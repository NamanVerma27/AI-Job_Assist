# backend/services/llm_router.py
"""
Lightweight LLM router:
- Try Groq client (if configured in llm_engine.client)
- Fallback to Google Gemini (if configured in llm_engine.genai)
- Final fallback: deterministic/local behavior (question bank or simple evaluator)
- No OpenAI calls, no auto-upgrade logic.
- Always returns a consistent dictionary shape and never raises to caller.
"""

import logging
import re
import random
from typing import Optional, Dict, Any

from backend.services import llm_engine  # reuse configured clients / constants
from backend.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Try to import question bank (optional). If missing, use static fallback.
try:
    from backend.services.mock.question_bank import SAMPLE_QUESTIONS
except Exception:
    SAMPLE_QUESTIONS = [
        "Tell me about a time you faced a technical challenge and how you solved it.",
        "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
        "Describe a project you led and the outcome.",
        "How do you prioritize tasks when given multiple deadlines?"
    ]


# ----------------------------
# Deterministic fallback utilities
# ----------------------------
_ACTION_VERBS = {
    "led", "managed", "developed", "implemented", "built", "designed", "improved",
    "optimized", "resolved", "deployed", "created", "automated", "engineered"
}

def _simple_evaluate_answer(answer: str) -> Dict[str, Any]:
    """
    Very small deterministic evaluator (safe fallback).
    Produces scores and short feedback consistent with existing UI expectation.
    """
    if not answer:
        return {
            "score": 0,
            "strengths": [],
            "weaknesses": ["No answer provided."],
            "feedback": "No answer provided.",
            "metrics": {"word_count": 0, "action_verbs": 0, "numeric_mentions": 0}
        }

    words = re.findall(r"\w+", answer)
    word_count = len(words)

    action_count = sum(1 for w in (w.lower() for w in words) if w in _ACTION_VERBS)
    numeric_mentions = len(re.findall(r"\d+[%$]?", answer))

    # length component: up to 40 points (target ~100 words)
    length_score = min(int((word_count / 100) * 40), 40)

    # action verbs: up to 30 points
    action_score = min(action_count * 8, 30)

    # numeric mentions: up to 30 points
    numeric_score = min(numeric_mentions * 10, 30)

    raw_score = length_score + action_score + numeric_score
    final_score = max(0, min(100, int(raw_score)))

    strengths = []
    weaknesses = []

    if action_count >= 1:
        strengths.append(f"Uses action verbs ({action_count}).")
    if numeric_mentions >= 1:
        strengths.append(f"Provides quantified evidence ({numeric_mentions}).")
    if word_count >= 60:
        strengths.append("Answer length is appropriate.")

    if word_count < 20:
        weaknesses.append("Answer is short; add more detail and examples.")
    if action_count == 0:
        weaknesses.append("No strong action verbs used; start bullets with strong verbs.")
    if numeric_mentions == 0:
        weaknesses.append("No quantified evidence provided; add numbers where possible.")

    feedback = f"Score: {final_score}/100 — length:{word_count}, action:{action_count}, quantified:{numeric_mentions}. "
    if strengths:
        feedback += "Strengths: " + "; ".join(strengths) + ". "
    if weaknesses:
        feedback += "Weaknesses: " + "; ".join(weaknesses) + "."

    return {
        "score": final_score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": feedback,
        "metrics": {
            "word_count": word_count,
            "action_verbs": action_count,
            "numeric_mentions": numeric_mentions,
            "raw_components": {
                "length_score": length_score,
                "action_score": action_score,
                "quantified_score": numeric_score
            }
        }
    }


# ----------------------------
# Public API
# ----------------------------
def ask_question(role: str = "general", difficulty: str = "Medium", prompt: Optional[str] = None) -> Dict[str, Any]:
    """
    Request the LLM to create / return the next question.
    Order:
      1) Groq (if configured)
      2) Gemini (if configured)
      3) Deterministic fallback (pick from question bank)
    Returns structured dict:
      { ok: bool, text: str, provider: "groq"|"gemini"|"fallback", raw: Any }
    """
    system_msg = f"You are a strict interviewer for a {role} role. Ask a concise relevant question."

    # Try Groq if client available
    try:
        client = getattr(llm_engine, "client", None)
        MODEL_NAME = getattr(llm_engine, "MODEL_NAME", None)
        if client:
            try:
                resp = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt or "Generate one interview question."}
                    ],
                    temperature=0.0,
                    max_tokens=300
                )
                raw_text = resp.choices[0].message.content or ""
                text = _clean_text(raw_text)
                if text:
                    return {"ok": True, "text": text, "provider": "groq", "raw": raw_text}
            except Exception as e:
                logger.exception("Groq failed in ask_question: %s", e)
    except Exception as e:
        # defensive
        logger.exception("Unexpected Groq attempt failure: %s", e)

    # Try Gemini (genai) if configured
    try:
        genai = getattr(llm_engine, "genai", None)
        if getattr(settings, "GEMINI_API_KEY", None) and genai:
            try:
                model = genai.GenerativeModel("gemini-pro")
                full_prompt = f"{system_msg}\n\n{prompt or 'Generate one interview question.'}"
                resp = model.generate_content(full_prompt)
                raw_text = getattr(resp, "text", "") or str(resp)
                text = _clean_text(raw_text)
                if text:
                    return {"ok": True, "text": text, "provider": "gemini", "raw": raw_text}
            except Exception as e:
                logger.exception("Gemini failed in ask_question: %s", e)
    except Exception as e:
        logger.exception("Unexpected Gemini attempt failure: %s", e)

    # Final deterministic fallback (question bank)
    try:
        fallback_q = random.choice(SAMPLE_QUESTIONS)
        return {"ok": True, "text": fallback_q, "provider": "fallback", "raw": None}
    except Exception as e:
        logger.exception("Fallback question selection failed: %s", e)
        return {"ok": False, "text": "Service unavailable", "provider": "none", "raw": None}


def evaluate_answer(answer: str, role: str = "general", context: Optional[str] = None) -> Dict[str, Any]:
    """
    Primary evaluation:
      - Try Groq -> Gemini for a detailed evaluation if available.
      - If both fail, use deterministic local evaluator.
    Returns dict shaped like:
      { ok: bool, provider: str, evaluation: {...}, raw: ... }
    """
    # Helper to call model with system prompt
    system_msg = f"You are an interviewer evaluating a candidate's answer for role: {role}. Provide a short numeric score out of 100, strengths, weaknesses and short feedback."

    # 1) Try Groq
    try:
        client = getattr(llm_engine, "client", None)
        MODEL_NAME = getattr(llm_engine, "MODEL_NAME", None)
        if client:
            try:
                messages = [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": f"Answer:\n{answer}\n\nProvide: score(0-100), strengths (list), weaknesses (list), feedback (short)."}
                ]
                resp = client.chat.completions.create(model=MODEL_NAME, messages=messages, temperature=0.05, max_tokens=400)
                raw_text = resp.choices[0].message.content or ""
                parsed = _parse_evaluation_text(raw_text)
                if parsed:
                    return {"ok": True, "provider": "groq", "evaluation": parsed, "raw": raw_text}
            except Exception as e:
                logger.exception("Groq failed in evaluate_answer: %s", e)
    except Exception as e:
        logger.exception("Unexpected Groq error: %s", e)

    # 2) Try Gemini if configured
    try:
        genai = getattr(llm_engine, "genai", None)
        if getattr(settings, "GEMINI_API_KEY", None) and genai:
            try:
                prompt = f"{system_msg}\n\nAnswer:\n{answer}\n\nProvide: score(0-100), strengths (list), weaknesses (list), feedback (short)."
                model = genai.GenerativeModel("gemini-pro")
                resp = model.generate_content(prompt)
                raw_text = getattr(resp, "text", "") or str(resp)
                parsed = _parse_evaluation_text(raw_text)
                if parsed:
                    return {"ok": True, "provider": "gemini", "evaluation": parsed, "raw": raw_text}
            except Exception as e:
                logger.exception("Gemini failed in evaluate_answer: %s", e)
    except Exception as e:
        logger.exception("Unexpected Gemini error: %s", e)

    # 3) Deterministic local evaluator
    try:
        eval_result = _simple_evaluate_answer(answer)
        return {"ok": True, "provider": "fallback", "evaluation": eval_result, "raw": None}
    except Exception as e:
        logger.exception("Local evaluator failed: %s", e)
        return {"ok": False, "provider": "none", "evaluation": None, "raw": None}


# ----------------------------
# Internal helpers
# ----------------------------
def _clean_text(raw: str) -> str:
    if not raw:
        return ""
    s = re.sub(r"```.*?```", "", raw, flags=re.DOTALL)
    s = s.replace("`", "").replace("**", "").strip()
    s = re.sub(r"\r\n", "\n", s)
    s = re.sub(r"\n{2,}", "\n\n", s)
    return s.strip()


def _parse_evaluation_text(raw: str) -> Optional[Dict[str, Any]]:
    """
    Try to extract a simple JSON-like or structured evaluation from raw LLM text.
    We do a best-effort parse: look for "Score:", "Strengths:", "Weaknesses:", "Feedback:".
    If we can't parse, return None so caller falls back to deterministic evaluator.
    """
    if not raw:
        return None
    text = _clean_text(raw)

    # Look for "Score: <num>"
    score_m = re.search(r"Score[:\s]*([0-9]{1,3})", text)
    score = int(score_m.group(1)) if score_m else None

    strengths = []
    weaknesses = []
    feedback = None

    # Simple block extraction
    strengths_m = re.search(r"Strengths[:\s]*\n?(.+?)(?:\n\n|Weaknesses:|Feedback:|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if strengths_m:
        strengths_text = strengths_m.group(1).strip()
        strengths = [s.strip("-* \t\n\r") for s in re.split(r"\n+", strengths_text) if s.strip()]

    weaknesses_m = re.search(r"Weaknesses[:\s]*\n?(.+?)(?:\n\n|Strengths:|Feedback:|$)", text, flags=re.DOTALL | re.IGNORECASE)
    if weaknesses_m:
        weaknesses_text = weaknesses_m.group(1).strip()
        weaknesses = [s.strip("-* \t\n\r") for s in re.split(r"\n+", weaknesses_text) if s.strip()]

    feedback_m = re.search(r"Feedback[:\s]*\n?(.+)$", text, flags=re.DOTALL | re.IGNORECASE)
    if feedback_m:
        feedback = feedback_m.group(1).strip()

    # If no score/content parsed, return None
    if score is None and not (strengths or weaknesses or feedback):
        return None

    # Fill defaults
    return {
        "score": score if score is not None else 0,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": feedback or "",
        "metrics": {}
    }
