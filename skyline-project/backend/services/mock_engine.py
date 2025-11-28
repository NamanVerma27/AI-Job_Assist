# backend/services/mock_engine.py
"""
Mock Interview Engine - Hybrid Evaluation (Deterministic + LLM)
---------------------------------------------------------------
Provides:
- deterministic_evaluate_answer(question, answer, resume_text=None)
- llm_evaluate_answer(question, answer, resume_text=None)
- evaluate_answer_hybrid(question, answer, resume_text=None, config={...})

Design:
- Deterministic evaluator is always run (fast, safe).
- If LLM is available and configured, we call it with a constrained prompt expecting JSON.
- We parse LLM JSON safely; if parsing fails or LLM times out, we fall back to deterministic result.
- Final score is a confidence-weighted blend of deterministic and llm scores.
"""

import re
import json
import logging
import time
from typing import Dict, Optional

from backend.services.text_cleaner import clean_text, redact_pii
# LLMEngine assumed present in your codebase (used earlier in other modules)
try:
    from backend.services.llm_engine import LLMEngine
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False

logger = logging.getLogger(__name__)

# Simple lists for signals (expand as needed)
ACTION_VERBS = [
    "developed", "created", "designed", "built", "implemented", "improved", "optimized",
    "led", "managed", "launched", "initiated", "enhanced", "engineered", "resolved",
    "coordinated", "executed", "drove", "modernized", "streamlined", "automated",
    "owned", "mentored", "supervised", "directed", "spearheaded"
]

LEADERSHIP_KEYWORDS = ["led", "managed", "supervised", "owned", "mentored", "directed", "coordinated", "spearheaded"]
HEDGING_RE = re.compile(r'\b(might|could|maybe|sometimes|possibly|may|might have)\b', flags=re.IGNORECASE)
NUMBER_RE = re.compile(r'\d+')

# -------------------------
# Deterministic evaluator
# -------------------------
def deterministic_evaluate_answer(question: str, answer: str, resume_text: Optional[str] = None) -> Dict:
    """
    Fast heuristic scoring. Returns a dict with `score`(0-100) and breakdown metrics.
    """
    q = (question or "").strip()
    a = (answer or "").strip()
    text_for_analysis = " ".join(filter(None, [q, a, resume_text or ""])).lower()

    if not a:
        return {
            "method": "deterministic",
            "score": 0,
            "reason": "No answer provided",
            "metrics": {}
        }

    # Basic metrics
    words = a.split()
    word_count = len(words)
    action_count = sum(1 for v in ACTION_VERBS if re.search(r'\b' + re.escape(v) + r'\b', a, flags=re.IGNORECASE))
    leadership_count = sum(1 for v in LEADERSHIP_KEYWORDS if re.search(r'\b' + re.escape(v) + r'\b', a, flags=re.IGNORECASE))
    number_count = len(NUMBER_RE.findall(a))
    hedging_count = len(HEDGING_RE.findall(a))

    # Length component (ideal range: 20-120 words for technical answers; tune as needed)
    if word_count < 6:
        length_score = 10
    elif word_count <= 25:
        length_score = 35
    elif word_count <= 80:
        length_score = 70
    else:
        length_score = 60  # long but can be okay

    # Action verbs component (normalized)
    action_score = min(30, action_count * 8)  # up to 30 points

    # Leadership component
    leadership_score = min(15, leadership_count * 6)  # up to 15

    # Quantified evidence
    quantified_score = min(25, number_count * 8)  # up to 25

    # Hedging penalty
    hedging_penalty = min(10, hedging_count * 5)

    # Compose raw total (cap at 100)
    raw = length_score + action_score + leadership_score + quantified_score - hedging_penalty
    final = max(0, min(100, int(round(raw))))

    strengths = []
    weaknesses = []
    if action_count > 0:
        strengths.append(f"Uses action verbs ({action_count}).")
    if leadership_count > 0:
        strengths.append(f"Shows leadership/ownership ({leadership_count}).")
    if number_count > 0:
        strengths.append(f"Provides quantified evidence ({number_count}).")
    if hedging_count > 0:
        weaknesses.append(f"Hedging language detected ({hedging_count}).")

    # short human text summary
    summary = f"Deterministic score: {final}/100 — length:{length_score}, action:{action_score}, leadership:{leadership_score}, quantified:{quantified_score}, hedging_penalty:{hedging_penalty}."

    return {
        "method": "deterministic",
        "score": final,
        "summary": summary,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "metrics": {
            "word_count": word_count,
            "action_count": action_count,
            "leadership_count": leadership_count,
            "number_count": number_count,
            "hedging_count": hedging_count,
            "length_score": length_score,
            "action_score": action_score,
            "leadership_score": leadership_score,
            "quantified_score": quantified_score,
            "hedging_penalty": hedging_penalty
        }
    }

# -------------------------
# LLM-based evaluator
# -------------------------
def llm_evaluate_answer(question: str, answer: str, resume_text: Optional[str] = None, timeout: int = 12) -> Optional[Dict]:
    """
    Calls LLMEngine to get a semantic evaluation. Expects JSON output.

    Returned structure (expected):
    {
      "method": "llm",
      "score": 72,              # 0-100
      "confidence": 0.78,      # model self-reported confidence (0..1) if provided
      "summary": "Short text",
      "strengths": [...],
      "weaknesses": [...],
      "suggested_rewrite": "Better phrasing..."
    }

    If LLM call fails or JSON is invalid, returns None.
    """
    if not LLM_AVAILABLE:
        return None

    # Clean & redact PII before sending to LLM (defensive)
    safe_question = clean_text(question or "", redact=True)
    safe_answer = clean_text(answer or "", redact=True)
    safe_resume = clean_text(resume_text or "", redact=True)

    # Construct strict instruction: JSON only, with schema
    prompt = f"""
You are an objective interview evaluator. Evaluate the candidate's answer to the given interview question.
Return output only as JSON (no surrounding text) with these fields:
- score (integer 0-100) : overall numeric quality of the answer.
- confidence (float 0.0-1.0) : how confident the model is in its score (optional but helpful).
- strengths (array of short strings).
- weaknesses (array of short strings).
- suggested_rewrite (string) : a single improved answer (concise).
- short_summary (string) : one-sentence explanation for the score.

Inputs:
Question: \"\"\"{safe_question}\"\"\"
Candidate Answer: \"\"\"{safe_answer}\"\"\"
Context (resume, optional): \"\"\"{safe_resume}\"\"\"

Constraints:
- Return ONLY JSON parsable by standard json.loads.
- Keep strings <= 400 characters except suggested_rewrite (up to 800 chars).
- If you cannot evaluate, return score: 0 and an explanatory short_summary.

Now output the JSON.
    """.strip()

    try:
        # Choose a task_type or model-specific param if you have them; use LLMEngine wrapper
        start_time = time.time()
        raw = LLMEngine.generate_response(prompt, task_type="mock_eval", timeout=timeout)
        elapsed = time.time() - start_time

        if not raw:
            return None

        # LLM wrappers sometimes return code fences — remove common wrappers
        clean = raw.strip()
        clean = clean.replace("```json", "").replace("```", "").strip()

        # Parse JSON safely
        parsed = json.loads(clean)
        # Normalize expected fields
        score = int(parsed.get("score", 0))
        confidence = float(parsed.get("confidence", 0.0) or 0.0)
        strengths = parsed.get("strengths", []) or []
        weaknesses = parsed.get("weaknesses", []) or []
        suggested_rewrite = parsed.get("suggested_rewrite") or parsed.get("rewrite") or ""
        short_summary = parsed.get("short_summary") or parsed.get("summary") or ""

        return {
            "method": "llm",
            "score": max(0, min(100, score)),
            "confidence": max(0.0, min(1.0, confidence)),
            "strengths": strengths,
            "weaknesses": weaknesses,
            "suggested_rewrite": suggested_rewrite,
            "short_summary": short_summary,
            "raw_llm_text": raw,
            "elapsed": elapsed
        }
    except Exception as e:
        logger.debug("LLM evaluation failed: %s", e, exc_info=True)
        return None

# -------------------------
# Hybrid evaluator (blending)
# -------------------------
def evaluate_answer_hybrid(question: str, answer: str, resume_text: Optional[str] = None, config: Dict = None) -> Dict:
    """
    Run deterministic evaluation, then optionally call LLM and blend results.

    Config (optional keys):
      "enable_llm": bool (default True if LLM available)
      "min_llm_confidence": float  (0..1) minimum LLM-reported confidence to consider using LLM (default 0.18)
      "min_word_count_for_llm": int (default 6) - skip LLM for extremely short answers
      "force_llm": bool (default False) - call LLM even if low word count
      "blend_base": float (0..1) base weight applied to deterministic result when LLM exists (overridden by llm confidence logic)
    """
    cfg = config or {}
    det = deterministic_evaluate_answer(question, answer, resume_text)

    # default config
    enable_llm = cfg.get("enable_llm", True) and LLM_AVAILABLE
    min_llm_conf = float(cfg.get("min_llm_confidence", 0.18))
    min_words = int(cfg.get("min_word_count_for_llm", 6))
    force_llm = bool(cfg.get("force_llm", False))

    # decide whether to call LLM
    word_count = det["metrics"].get("word_count", 0)
    llm_result = None
    if enable_llm and (word_count >= min_words or force_llm):
        try:
            llm_result = llm_evaluate_answer(question, answer, resume_text, timeout=int(cfg.get("llm_timeout", 12)))
        except Exception as e:
            logger.debug("LLM call raised: %s", e, exc_info=True)
            llm_result = None

    # If no LLM result, return deterministic
    if not llm_result:
        return {
            "final_method": "deterministic",
            "final_score": det["score"],
            "deterministic": det,
            "llm": None,
            "blend": {
                "used_llm": False
            }
        }

    # Compute blending weights based on LLM confidence
    # Map LLM confidence [0..1] to llm_weight in [0.25 .. 0.85] (tunable)
    llm_conf = float(llm_result.get("confidence", 0.0) or 0.0)
    # If LLM doesn't supply confidence, infer moderately high trust for longer answers
    if llm_conf <= 0:
        if word_count >= 40:
            llm_conf = 0.7
        elif word_count >= 15:
            llm_conf = 0.55
        else:
            llm_conf = 0.40

    # only accept LLM influence above threshold
    if llm_conf < min_llm_conf:
        return {
            "final_method": "deterministic",
            "final_score": det["score"],
            "deterministic": det,
            "llm": llm_result,
            "blend": {
                "used_llm": False,
                "reason": "llm_conf_too_low",
                "llm_confidence": llm_conf
            }
        }

    # compute llm_weight
    llm_weight = min(0.85, 0.25 + 0.75 * llm_conf)
    det_weight = 1.0 - llm_weight

    # final blended score
    det_score = float(det.get("score", 0))
    llm_score = float(llm_result.get("score", 0))
    blended = int(round(det_score * det_weight + llm_score * llm_weight))

    # Merge strengths/weaknesses (dedup keep order)
    def merge_lists(a, b):
        out = []
        s = set()
        for x in (a or []) + (b or []):
            key = (x or "").strip().lower()
            if key and key not in s:
                s.add(key)
                out.append(x)
        return out

    strengths = merge_lists(det.get("strengths", []), llm_result.get("strengths", []))
    weaknesses = merge_lists(det.get("weaknesses", []), llm_result.get("weaknesses", []))

    return {
        "final_method": "hybrid",
        "final_score": blended,
        "weights": {"llm_weight": round(llm_weight, 3), "deterministic_weight": round(det_weight, 3), "llm_confidence": round(llm_conf, 3)},
        "deterministic": det,
        "llm": llm_result,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "suggested_rewrite": llm_result.get("suggested_rewrite"),
        "blend": {
            "used_llm": True,
            "det_score": det_score,
            "llm_score": llm_score,
            "blended_score": blended
        }
    }
