# backend/services/mock/llm_evaluator.py
import logging
import re
import inspect
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import project LLM engine; tests will patch this module-level name.
# The engine export may be a class or an instance; handle both.
try:
    from backend.services.llm_engine import LLMEngine as LLM_ENGINE  # type: ignore
except Exception:
    LLM_ENGINE = None  # tests and runtime can patch this

# If LLM_ENGINE is a class, instantiate it (best-effort). If it's already an instance, keep it.
try:
    if LLM_ENGINE and inspect.isclass(LLM_ENGINE):
        try:
            LLM_ENGINE = LLM_ENGINE()
        except Exception:
            # If instantiation fails, leave as-is — tests may monkeypatch LLM_ENGINE later.
            logger.debug("LLM_ENGINE is a class but instantiation failed; leaving as-is for tests to patch.", exc_info=True)
except Exception:
    pass

# Deterministic fallback implementations (kept simple and stable).
# Prefer to use mock.question_bank if available (it supports difficulty)
try:
    from backend.services.mock.question_bank import get_random_question as _question_bank_get_random
    _QUESTION_BANK_AVAILABLE = True
except Exception:
    _QUESTION_BANK_AVAILABLE = False
    _question_bank_get_random = None


def deterministic_get_question(role: str = "general", difficulty: Optional[str] = None) -> Dict[str, str]:
    """
    Return a deterministic question. Prefer the project's question_bank if available
    (supports difficulty). Otherwise use an internal small pool.
    Returns a dict: {"text": <question_text>}
    """
    # If integrated question bank exists, use it (it returns a string)
    try:
        if _QUESTION_BANK_AVAILABLE and _question_bank_get_random:
            try:
                text = _question_bank_get_random(role, difficulty or "Medium")
                return {"text": str(text)}
            except Exception:
                logger.debug("question_bank.get_random_question errored; falling back to internal pool.", exc_info=True)
    except Exception:
        logger.debug("error while trying question bank.", exc_info=True)

    # Internal fallback pool (role keys normalized to lowercase)
    pool = {
        "frontend": {
            "Easy": "What is the DOM and how does virtual DOM differ?",
            "Medium": "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
            "Hard": "Explain how React Fiber works internally."
        },
        "backend": {
            "Easy": "Explain REST vs SOAP.",
            "Medium": "Explain database indexing and when NOT to use an index.",
            "Hard": "Describe how you'd scale a high-read, low-write API across regions."
        },
        "general": {
            "Easy": "Tell me about yourself.",
            "Medium": "How do you prioritize tasks when given multiple deadlines?",
            "Hard": "Describe a major project you led end-to-end. What was the impact?"
        }
    }

    r = (role or "general").lower().strip()
    diff = (difficulty or "Medium").capitalize().strip()

    if r not in pool:
        r = "general"

    candidate = pool.get(r, {}).get(diff)
    if candidate:
        return {"text": candidate}

    # Try same role any difficulty
    for v in pool.get(r, {}).values():
        if v:
            return {"text": v}

    # Global fallback
    return {"text": pool["general"]["Medium"]}


def deterministic_evaluate_answer(answer: str, role: str = "general") -> Dict[str, Any]:
    """
    Simple deterministic evaluator returning a stable schema:
        {"score": int, "feedback": str, "strengths": [...], "weaknesses": [...], "metrics": {...}}
    """
    if not answer or not answer.strip():
        return {"score": 0, "feedback": "No answer provided.", "strengths": [], "weaknesses": ["No answer."], "metrics": {}}

    words = answer.split()
    word_count = len(words)
    action_verbs = sum(
        1 for w in words
        if w.lower().strip(".,!?:;()[]") in (
            "built", "developed", "designed", "implemented", "led", "improved", "fixed", "deployed"
        )
    )
    numbers = len(re.findall(r"\d+", answer))

    # naive scoring
    score = min(100, max(5, (word_count * 3) + (action_verbs * 10) + (numbers * 8)))

    strengths = []
    weaknesses = []
    if action_verbs:
        strengths.append("Uses action verbs.")
    if numbers:
        strengths.append("Provides quantified evidence.")
    if word_count < 15:
        weaknesses.append("Answer is short; add more detail.")

    feedback = f"Score: {score}/100 — length:{word_count}, action:{action_verbs}, quantified:{numbers}."
    return {
        "score": score,
        "feedback": feedback,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "metrics": {"word_count": word_count, "action_verbs": action_verbs, "numeric_mentions": numbers}
    }


# ---------------------------
# Public helpers used by routers/tests
# ---------------------------

def ask_question(role: str = "general", difficulty: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns: {"text": "...", "provider": "llm" | "fallback"}

    Behavior:
      - If an LLM engine is available, call it with a difficulty-aware prompt.
      - If the LLM returns a non-empty usable string, return provider 'llm'.
      - Otherwise, fall back to deterministic_get_question(role, difficulty) and return provider 'fallback'.
      - Never raises to caller; all exceptions are caught and logged.
    """
    try:
        # 1) LLM FIRST (if available)
        if LLM_ENGINE:
            try:
                # Build difficulty-aware prompt (simple)
                prompt = (
                    f"Generate a {difficulty or 'Medium'} difficulty interview question "
                    f"for the role '{role}'. Return only the question text."
                )

                # Support both instances and callables. Safe call inside try/except.
                if hasattr(LLM_ENGINE, "generate_response") and callable(LLM_ENGINE.generate_response):
                    resp = LLM_ENGINE.generate_response(prompt=prompt, task_type="mock_interview", role=role)
                else:
                    # If LLM_ENGINE is a callable function
                    try:
                        resp = LLM_ENGINE(prompt=prompt, task_type="mock_interview", role=role)  # type: ignore
                    except Exception:
                        resp = None

                if resp and isinstance(resp, str) and resp.strip():
                    return {"text": resp.strip(), "provider": "llm"}

                # If LLM returns dict-like with a text key, accept that too
                if isinstance(resp, dict):
                    for k in ("text", "question", "question_text", "q"):
                        if resp.get(k):
                            t = resp.get(k)
                            if isinstance(t, str) and t.strip():
                                return {"text": t.strip(), "provider": "llm"}
                # else fallthrough to deterministic

            except Exception:
                logger.debug("LLM ask_question error; falling back to deterministic.", exc_info=True)

        # 2) deterministic fallback (difficulty-aware)
        det = deterministic_get_question(role, difficulty)
        if isinstance(det, dict):
            for k in ("text", "question", "question_text", "q"):
                if det.get(k):
                    t = det.get(k)
                    if isinstance(t, str) and t.strip():
                        return {"text": t.strip(), "provider": "fallback"}
            # join any string values
            candidates = [str(v).strip() for v in det.values() if isinstance(v, str) and v.strip()]
            if candidates:
                return {"text": " ".join(candidates).strip(), "provider": "fallback"}
            return {"text": str(det), "provider": "fallback"}

        # If det returned plain string
        return {"text": str(det).strip(), "provider": "fallback"}

    except Exception:
        logger.exception("ask_question fatal error (fallback attempt).")
        # Safe fallback
        return {"text": "Tell me about yourself.", "provider": "fallback"}


def _parse_score_from_text(text: str) -> Optional[int]:
    """
    Try to find a numeric score in the LLM output.

    Accept patterns like:
      - "Score: 88"
      - "Score 88"
      - JSON like {"score": 88}
    """
    if not text or not isinstance(text, str):
        return None

    # Try JSON-ish score
    mjson = re.search(r'"score"\s*:\s*(\d{1,3})', text)
    if mjson:
        try:
            return int(mjson.group(1))
        except Exception:
            pass

    # Try "Score: 88" or "Score 88"
    m = re.search(r'\bScore[:\s]*([0-9]{1,3})\b', text, flags=re.IGNORECASE)
    if m:
        try:
            return int(m.group(1))
        except Exception:
            pass

    # Try top-level integer on a line
    mline = re.search(r'^\s*([0-9]{1,3})\s*$', text, flags=re.MULTILINE)
    if mline:
        try:
            return int(mline.group(1))
        except Exception:
            pass

    return None


def evaluate_answer(answer: str, role: str = "general") -> Dict[str, Any]:
    """
    Evaluate the user's answer.

    Returns a dict:
      {
        "ok": True|False,
        "provider": "llm"|"deterministic"|"none",
        "evaluation": { score, feedback, strengths, weaknesses, ... }
      }

    Behavior:
      - If answer missing -> ok=False, provider=none
      - If LLM available -> try LLM, parse its score -> if parseable -> provider=llm
      - If LLM output empty/unparseable OR LLM not available -> deterministic fallback -> provider=deterministic
      - Always catch exceptions and never raise to caller
    """
    try:
        if not answer or not answer.strip():
            return {"ok": False, "provider": "none", "evaluation": {"score": 0, "feedback": "No answer provided."}}

        # If there's an LLM, try it first
        if LLM_ENGINE:
            try:
                # Try generating an evaluation from the LLM
                if hasattr(LLM_ENGINE, "generate_response") and callable(LLM_ENGINE.generate_response):
                    raw = LLM_ENGINE.generate_response(prompt=answer, task_type="mock_eval", role=role)
                else:
                    try:
                        raw = LLM_ENGINE(prompt=answer, task_type="mock_eval", role=role)  # type: ignore
                    except Exception:
                        raw = None

                # If LLM returned nothing -> fallback deterministic
                if not raw or (isinstance(raw, str) and not raw.strip()):
                    logger.debug("LLM returned empty response; falling back to deterministic evaluator.")
                    eval_det = deterministic_evaluate_answer(answer, role)
                    return {"ok": True, "provider": "deterministic", "evaluation": eval_det}

                # If raw is dict with evaluation-like content, try to normalize
                if isinstance(raw, dict):
                    # expected shape e.g. {"score": 88, "feedback": "..."}
                    score = raw.get("score")
                    feedback = raw.get("feedback") or raw.get("message") or ""
                    strengths = raw.get("strengths") or []
                    weaknesses = raw.get("weaknesses") or []
                    evaluation = {
                        "score": int(score) if isinstance(score, (int, float, str)) and str(score).isdigit() else None,
                        "feedback": str(feedback) if feedback is not None else "",
                        "strengths": strengths if isinstance(strengths, list) else [],
                        "weaknesses": weaknesses if isinstance(weaknesses, list) else [],
                        "raw": raw
                    }
                    if evaluation["score"] is not None:
                        return {"ok": True, "provider": "llm", "evaluation": evaluation}
                    # else fallthrough to try parse text or fallback

                # If LLM returned text, try parse score
                if isinstance(raw, str):
                    score = _parse_score_from_text(raw)
                    if score is None:
                        logger.debug("LLM response unparsable; falling back to deterministic evaluator. Raw (truncated): %s", (raw[:200] if raw else raw))
                        eval_det = deterministic_evaluate_answer(answer, role)
                        return {"ok": True, "provider": "deterministic", "evaluation": eval_det}

                    # Build evaluation object from LLM text (best-effort)
                    strengths = []
                    weaknesses = []
                    try:
                        s_match = re.search(r'Strengths:\s*(.+?)(Weaknesses:|Feedback:|$)', raw, flags=re.DOTALL | re.IGNORECASE)
                        if s_match:
                            s_text = s_match.group(1).strip()
                            strengths = [s.strip() for s in re.split(r'\n|\d+\.\s*', s_text) if s.strip()]
                    except Exception:
                        strengths = []

                    try:
                        w_match = re.search(r'Weaknesses:\s*(.+?)(Strengths:|Feedback:|$)', raw, flags=re.DOTALL | re.IGNORECASE)
                        if w_match:
                            w_text = w_match.group(1).strip()
                            weaknesses = [w.strip() for w in re.split(r'\n|\d+\.\s*', w_text) if w.strip()]
                    except Exception:
                        weaknesses = []

                    f_match = re.search(r'Feedback:\s*(.+)$', raw, flags=re.DOTALL | re.IGNORECASE)
                    if f_match:
                        fb = f_match.group(1).strip()
                    else:
                        fb = raw.strip()[:800]

                    evaluation = {
                        "score": int(score),
                        "feedback": fb,
                        "strengths": strengths,
                        "weaknesses": weaknesses,
                        "raw": raw
                    }
                    return {"ok": True, "provider": "llm", "evaluation": evaluation}

            except Exception:
                logger.exception("LLM evaluation failed; falling back to deterministic evaluator.")
                eval_det = deterministic_evaluate_answer(answer, role)
                return {"ok": True, "provider": "deterministic", "evaluation": eval_det}

        # No LLM available -> deterministic
        eval_det = deterministic_evaluate_answer(answer, role)
        return {"ok": True, "provider": "deterministic", "evaluation": eval_det}

    except Exception:
        logger.exception("evaluate_answer fatal error, returning safe failure.")
        return {"ok": False, "provider": "none", "evaluation": {"score": 0, "feedback": "Internal error during evaluation."}}
