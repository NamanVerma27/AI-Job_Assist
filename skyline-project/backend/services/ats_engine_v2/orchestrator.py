"""
backend/services/ats_engine_v2/orchestrator.py

Production-ready orchestrator for ATS v2.

Notes:
- Defensively calls each module.
- Normalizes weights and clamps final_score to 0-100.
- Always includes safe minimal raw keys (total_keyword_score, breakdown, raw_counts, tiers_detected)
  so tests and frontends won't KeyError when accessing expected fields.
- export_raw config toggles returning full module outputs vs compact summary.
- Adds meta. Version: 2.0
"""

from typing import Dict, Any
from .ats_config import ATS_CONFIG
from .structure_analyzer import analyze_structure
from .keyword_engine import analyze_keywords
from .semantic_engine import compute_semantic_similarity
from .readability import analyze_readability
from .tone_analyzer import analyze_tone
from .role_detector import detect_role
from .insights import generate_insights

_DEFAULT_WEIGHTS = {
    "structure": 0.2,
    "keywords": 0.2,
    "semantics": 0.2,
    "readability": 0.2,
    "tone": 0.2
}

def _safe_call(func, *args, name: str = "module", default=None, **kwargs):
    """
    Helper to call module functions defensively.
    Returns default on exception (and logs server-side).
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        print(f"[ATS v2] {name} error:", e)
        return default if default is not None else {}

def run_ats_v2(resume_text: str, jd_text: str) -> Dict[str, Any]:
    """
    Main entrypoint for ATS v2.
    Returns dict:
      - meta
      - total_score
      - scores (per module)
      - role
      - insights
      - raw (either full or compact but always contains expected keys)
    """

    cfg = ATS_CONFIG or {}
    enable_structure = cfg.get("enable_structure", True)
    enable_keywords = cfg.get("enable_keywords", True)
    enable_semantics = cfg.get("enable_semantics", True)
    enable_readability = cfg.get("enable_readability", True)
    enable_tone = cfg.get("enable_tone", True)
    enable_role_detection = cfg.get("enable_role_detection", True)
    enable_insights = cfg.get("enable_insights", True)
    export_raw = cfg.get("export_raw", False)  # set True for debugging; False in prod

    weights = cfg.get("weights", _DEFAULT_WEIGHTS)

    # -------------------------
    # Run modules defensively
    # -------------------------
    structure_result = _safe_call(analyze_structure, resume_text, name="structure_analyzer", default={}) if enable_structure else {}
    # analyze_keywords(jd_text, resume_text)
    keyword_result = _safe_call(analyze_keywords, jd_text, resume_text, name="keyword_engine", default={}) if enable_keywords else {}
    semantic_result = _safe_call(compute_semantic_similarity, resume_text, jd_text, name="semantic_engine", default={}) if enable_semantics else {}
    readability_result = _safe_call(analyze_readability, resume_text, name="readability", default={}) if enable_readability else {}
    tone_result = _safe_call(analyze_tone, resume_text, name="tone_analyzer", default={}) if enable_tone else {}
    role_result = _safe_call(detect_role, resume_text, name="role_detector", default={}) if enable_role_detection else {}

    # -------------------------
    # Normalize module scores (consistent keys)
    # -------------------------
    struct_s = structure_result.get("structure_score", structure_result.get("score", 0) or 0)
    key_s = keyword_result.get("total_keyword_score", keyword_result.get("keyword_score", 0) or 0)
    sem_s = semantic_result.get("semantic_score", semantic_result.get("score", 0) or 0)
    read_s = readability_result.get("readability_score", readability_result.get("score", 0) or 0)
    tone_s = tone_result.get("tone_score", tone_result.get("score", 0) or 0)

    # Ensure numeric floats
    def _to_float_safe(v):
        try:
            return float(v)
        except Exception:
            return 0.0

    struct_s = _to_float_safe(struct_s)
    key_s = _to_float_safe(key_s)
    sem_s = _to_float_safe(sem_s)
    read_s = _to_float_safe(read_s)
    tone_s = _to_float_safe(tone_s)

    # -------------------------
    # Weighted final score (normalize weights)
    # -------------------------
    w_structure = weights.get("structure", _DEFAULT_WEIGHTS["structure"])
    w_keywords = weights.get("keywords", _DEFAULT_WEIGHTS["keywords"])
    w_semantics = weights.get("semantics", _DEFAULT_WEIGHTS["semantics"])
    w_readability = weights.get("readability", _DEFAULT_WEIGHTS["readability"])
    w_tone = weights.get("tone", _DEFAULT_WEIGHTS["tone"])

    w_sum = sum([w_structure, w_keywords, w_semantics, w_readability, w_tone])
    if w_sum <= 0:
        w_sum = 1.0

    weighted_value = (
        struct_s * w_structure +
        key_s * w_keywords +
        sem_s * w_semantics +
        read_s * w_readability +
        tone_s * w_tone
    ) / w_sum

    final_score = int(round(max(0.0, min(100.0, weighted_value))))

    # -------------------------
    # Insights
    # -------------------------
    insights_input = {
        "structure": structure_result,
        "keywords": keyword_result,
        "semantics": semantic_result,
        "readability": readability_result,
        "tone": tone_result,
        "role": role_result
    }
    insights = _safe_call(generate_insights, insights_input, name="generate_insights", default={}) if enable_insights else {}

    # -------------------------
    # Raw keywords safe structure (always include expected keys)
    # -------------------------
    raw_keywords = {
        "total_keyword_score": keyword_result.get("total_keyword_score", keyword_result.get("keyword_score", 0)),
        "breakdown": keyword_result.get("breakdown", {}),
        "raw_counts": keyword_result.get("raw_counts", {}),         # <-- ALWAYS include this key
        "tiers_detected": keyword_result.get("tiers_detected", {})
    }

    # Full raw payload (unpruned)
    raw_payload_full = {
        "structure": structure_result,
        "keywords": raw_keywords,
        "semantics": semantic_result,
        "readability": readability_result,
        "tone": tone_result,
        "role": role_result
    }

    # -------------------------
    # Compact raw payload (safe minimal, includes raw_counts)
    # -------------------------
    raw_payload_compact = {
        "keywords": {
            "total_keyword_score": raw_keywords["total_keyword_score"],
            "breakdown": raw_keywords.get("breakdown", {}),
            "raw_counts": raw_keywords.get("raw_counts", {}),      # <-- present even in compact
            "tiers_detected": raw_keywords.get("tiers_detected", {})
        },
        "structure": {"structure_score": structure_result.get("structure_score")} if structure_result else {},
        "semantics": {"semantic_score": semantic_result.get("semantic_score")} if semantic_result else {},
        "readability": {"readability_score": readability_result.get("readability_score")} if readability_result else {},
        "tone": {"tone_score": tone_result.get("tone_score")} if tone_result else {},
        "role": role_result if role_result else {}
    }

    # If export_raw disabled, optionally truncate large text fields in full payload
    if not export_raw:
        # Do not return the full payload; return compact (but with expected keys).
        raw_out = raw_payload_compact
    else:
        # For full payload, do light truncation of obvious big text fields
        # (avoid returning multi-MB resume text)
        def _truncate_large_texts(obj):
            if isinstance(obj, dict):
                for k, v in list(obj.items()):
                    if k.lower() in ("content", "text", "resume_text", "jd_text"):
                        if isinstance(v, str) and len(v) > 2000:
                            obj[k] = v[:2000] + "...[truncated]"
                    elif isinstance(v, dict):
                        _truncate_large_texts(v)
                return obj
            return obj
        _truncate_large_texts(raw_payload_full)
        raw_out = raw_payload_full

    # -------------------------
    # Response
    # -------------------------
    response: Dict[str, Any] = {
        "meta": {
            "ats_v": "2.0",
            "export_raw": bool(export_raw)
        },
        "total_score": final_score,
        "scores": {
            "structure": int(round(max(0, min(100, struct_s)))),
            "keywords": int(round(max(0, min(100, key_s)))),
            "semantics": int(round(max(0, min(100, sem_s)))),
            "readability": int(round(max(0, min(100, read_s)))),
            "tone": int(round(max(0, min(100, tone_s))))
        },
        "role": role_result,
        "insights": insights,
        "raw": raw_out
    }

    return response
