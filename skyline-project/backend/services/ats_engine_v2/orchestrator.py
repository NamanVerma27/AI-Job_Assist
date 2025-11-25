# backend/services/ats_engine_v2/orchestrator.py
"""
Improved ATS v2 Orchestrator
Schema-aligned with the new test suite expectations.

Key Changes:
- Adds a clean, stable `breakdown` object: {module: {score, weight}}
- Ensures raw.keywords always has:
    total_keyword_score, breakdown, raw_counts, tiers_detected
- Ensures final_score = weighted sum of module scores
- Keeps meta + insights + role exactly as required
- Compact raw output by default (export_raw flag to get full outputs)
- Version: 2.0
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
    "structure": 0.18,
    "keywords": 0.30,
    "semantics": 0.22,
    "readability": 0.15,
    "tone": 0.15
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

    Returns improved schema:
    {
      "meta": {...},
      "total_score": int,
      "breakdown": { module: { score: int, weight: float } , ... },
      "role": {...},
      "insights": {...},
      "raw": { "keywords": {...}, "structure": {...}, ... }
    }
    """

    cfg = ATS_CONFIG or {}
    enable_structure   = cfg.get("enable_structure", True)
    enable_keywords    = cfg.get("enable_keywords", True)
    enable_semantics   = cfg.get("enable_semantics", True)
    enable_readability = cfg.get("enable_readability", True)
    enable_tone        = cfg.get("enable_tone", True)
    enable_role        = cfg.get("enable_role_detection", True)
    enable_insights    = cfg.get("enable_insights", True)

    export_raw = cfg.get("export_raw", False)
    weights = cfg.get("weights", _DEFAULT_WEIGHTS)

    # -------------------------
    # Execute ATS modules (defensively)
    # -------------------------
    structure_result = (
        _safe_call(analyze_structure, resume_text, name="structure_analyzer", default={})
        if enable_structure else {}
    )

    # IMPORTANT: analyze_keywords signature is (jd_text, resume_text)
    keyword_result = (
        _safe_call(analyze_keywords, jd_text, resume_text, name="keyword_engine", default={})
        if enable_keywords else {}
    )

    semantic_result = (
        _safe_call(compute_semantic_similarity, resume_text, jd_text, name="semantic_engine", default={})
        if enable_semantics else {}
    )

    readability_result = (
        _safe_call(analyze_readability, resume_text, name="readability", default={})
        if enable_readability else {}
    )

    tone_result = (
        _safe_call(analyze_tone, resume_text, name="tone_analyzer", default={})
        if enable_tone else {}
    )

    role_result = (
        _safe_call(detect_role, resume_text, name="role_detector", default={})
        if enable_role else {}
    )

    # -------------------------
    # Normalize numeric scores (safe)
    # -------------------------
    def safe_num(value):
        try:
            return float(value)
        except Exception:
            return 0.0

    struct_s = safe_num(structure_result.get("structure_score", structure_result.get("score", 0)))
    key_s    = safe_num(keyword_result.get("total_keyword_score", keyword_result.get("keyword_score", 0)))
    sem_s    = safe_num(semantic_result.get("semantic_score", semantic_result.get("score", 0)))
    read_s   = safe_num(readability_result.get("readability_score", readability_result.get("score", 0)))
    tone_s   = safe_num(tone_result.get("tone_score", tone_result.get("score", 0)))

    # -------------------------
    # Weighted final score
    # -------------------------
    w_structure   = weights.get("structure",   _DEFAULT_WEIGHTS["structure"])
    w_keywords    = weights.get("keywords",    _DEFAULT_WEIGHTS["keywords"])
    w_semantics   = weights.get("semantics",   _DEFAULT_WEIGHTS["semantics"])
    w_readability = weights.get("readability", _DEFAULT_WEIGHTS["readability"])
    w_tone        = weights.get("tone",        _DEFAULT_WEIGHTS["tone"])

    total_w = w_structure + w_keywords + w_semantics + w_readability + w_tone
    if total_w <= 0:
        total_w = 1.0

    weighted_score = (
        struct_s * w_structure +
        key_s    * w_keywords +
        sem_s    * w_semantics +
        read_s   * w_readability +
        tone_s   * w_tone
    ) / total_w

    final_score = int(round(max(0, min(100, weighted_score))))

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

    insights = (
        _safe_call(generate_insights, insights_input, name="generate_insights", default={})
        if enable_insights else {}
    )

    # -------------------------
    # Construct improved breakdown
    # -------------------------
    breakdown = {
        "structure":   {"score": int(round(struct_s)), "weight": float(w_structure)},
        "keywords":    {"score": int(round(key_s)),    "weight": float(w_keywords)},
        "semantics":   {"score": int(round(sem_s)),    "weight": float(w_semantics)},
        "readability": {"score": int(round(read_s)),   "weight": float(w_readability)},
        "tone":        {"score": int(round(tone_s)),   "weight": float(w_tone)}
    }

    # -------------------------
    # Raw: always include mandatory keyword keys (canonical shape)
    # -------------------------
    raw_keywords = {
        "total_keyword_score": keyword_result.get("total_keyword_score", keyword_result.get("keyword_score", 0)),
        "breakdown":           keyword_result.get("breakdown", {}),
        "raw_counts":          keyword_result.get("raw_counts", {}),
        "tiers_detected":      keyword_result.get("tiers_detected", {})
    }

    # Build raw output (compact vs full)
    raw_out_compact = {
        "keywords": raw_keywords,
        "structure": {"structure_score": structure_result.get("structure_score", None)} if structure_result else {},
        "semantics": {"semantic_score": semantic_result.get("semantic_score", None)} if semantic_result else {},
        "readability": {"readability_score": readability_result.get("readability_score", None)} if readability_result else {},
        "tone": {"tone_score": tone_result.get("tone_score", None)} if tone_result else {},
        "role": role_result or {}
    }

    if export_raw:
        # Return full module outputs but truncate obvious large fields
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
        full_raw = {
            "keywords": raw_keywords,
            "structure": structure_result,
            "semantics": semantic_result,
            "readability": readability_result,
            "tone": tone_result,
            "role": role_result
        }
        _truncate_large_texts(full_raw)
        raw_out = full_raw
    else:
        raw_out = raw_out_compact

    # -------------------------
    # Final response structure (improved schema)
    # -------------------------
    response: Dict[str, Any] = {
        "meta": {"ats_v": "2.0", "export_raw": bool(export_raw)},
        "total_score": final_score,
        "breakdown": breakdown,
        "role": role_result,
        "insights": insights,
        "raw": raw_out
    }

    return response
