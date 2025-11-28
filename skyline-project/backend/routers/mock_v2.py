# backend/routers/mock_v2.py
"""
Mock Interview Router (v2)
--------------------------

Provides a deterministic, safe, and fast mock-interview flow for Phase 1.
This router avoids calling LLMs and instead uses simple heuristics to evaluate answers:
 - length (word count)
 - presence of action verbs
 - leadership/ownership keywords
 - quantified achievements (numbers)
All evaluations are deterministic and explainable (suitable for UI flows and tests).

Sessions are stored in-memory (SESSIONS). For production you should persist sessions in a DB.
"""

import time
import uuid
from typing import Dict, Any, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel



# Question bank utilities (ensure this module exists: backend/services/mock/question_bank.py)
try:
    from backend.services.mock.question_bank import get_random_question, get_question_by_id
except Exception:
    # If missing, provide helpful error at import time so developer sees the issue
    raise

router = APIRouter(prefix="/mock", tags=["Mock Interviews (v2)"])

# In-memory session store (session_id -> session data)
# session data schema:
# {
#   "role": str,
#   "created_at": float,
#   "last_question": { "id": str, "question": str },
#   "asked": [ { "id": str, "question": str, "answer": str, "score": int, "meta": {...} } ],
#   "use_llm": bool
# }
SESSIONS: Dict[str, Dict[str, Any]] = {}

# --- Request/Response models ---
class StartReq(BaseModel):
    role: str
    use_llm: Optional[bool] = False  # reserved for later hybrid mode

class StartResp(BaseModel):
    status: str
    data: Dict[str, Any]

class SessionIdReq(BaseModel):
    session_id: str

class AnswerReq(BaseModel):
    session_id: str
    answer: str

class QuestionResp(BaseModel):
    status: str
    data: Dict[str, Any]

class EvalResult(BaseModel):
    score: int
    strengths: list
    weaknesses: list
    feedback: str
    metrics: dict

# --- Deterministic evaluation helpers ---
ACTION_VERBS = {
    "developed","created","designed","built","implemented","improved","optimized",
    "led","managed","launched","initiated","enhanced","engineered","resolved",
    "coordinated","executed","drove","streamlined","automated","owned","mentored",
    "supervised","directed","spearheaded","orchestrated"
}

LEADERSHIP_KEYWORDS = {"led","managed","supervised","owned","mentored","directed","coordinated","spearheaded"}

HEDGING_WORDS = {"maybe","might","could","possibly","sometimes","may","might've"}

def _word_tokens(text: str):
    return [t.strip(".,;:()[]{}\"'") for t in text.split() if t.strip()]

def _count_numbers(text: str) -> int:
    # simple numeric token detection
    tokens = _word_tokens(text)
    cnt = 0
    for t in tokens:
        # contains digits like "3", "3+", "20%"
        if any(ch.isdigit() for ch in t):
            cnt += 1
    return cnt

def _count_action_verbs(text: str) -> int:
    t = text.lower()
    cnt = 0
    for v in ACTION_VERBS:
        if f" {v} " in f" {t} " or t.startswith(v + " ") or t.endswith(" " + v):
            cnt += t.count(v)
    return cnt

def _count_leadership(text: str) -> int:
    t = text.lower()
    cnt = 0
    for v in LEADERSHIP_KEYWORDS:
        if f" {v} " in f" {t} " or t.startswith(v + " ") or t.endswith(" " + v):
            cnt += t.count(v)
    return cnt

def _count_hedging(text: str) -> int:
    t = text.lower()
    cnt = 0
    for w in HEDGING_WORDS:
        if f" {w} " in f" {t} ":
            cnt += 1
    return cnt

def deterministic_evaluate(answer: str) -> Dict[str, Any]:
    """
    Deterministic scoring:
      - baseline length_score (0..40) based on word count
      - action_score (0..25) based on action verb density
      - leadership_score (0..20) for leadership words/ownership signals
      - quantified_score (0..15) for presence of numeric achievements
      - hedging_penalty (- up to 10)
    Final score is clipped to 0..100.

    Returns dict containing score, metrics, strengths, weaknesses, and short feedback.
    """
    if not answer or not answer.strip():
        return {
            "score": 0,
            "metrics": {},
            "strengths": [],
            "weaknesses": ["No answer provided."],
            "feedback": "No answer submitted."
        }

    tokens = _word_tokens(answer)
    word_count = len(tokens)
    num_count = _count_numbers(answer)
    action_count = _count_action_verbs(answer)
    lead_count = _count_leadership(answer)
    hedge_count = _count_hedging(answer)

    # 1. Length (words) — encourage 20-120 words (concise but informative)
    if word_count < 15:
        length_score = int(max(0, (word_count / 15) * 20))  # up to 20
    elif word_count <= 80:
        # full credit in middle range
        length_score = 20
    else:
        # slightly penalize very long answers
        length_score = int(max(10, 20 - ((word_count - 80) / 40) * 10))  # not harsh

    # 2. Action verbs density (action_count per 10 sentences/phrases)
    action_score = int(min(25, action_count * 5))  # each action verb gives 5 points up to 25

    # 3. Leadership/ownership
    leadership_score = int(min(20, lead_count * 7))  # each mention gives ~7 pts up to 20

    # 4. Quantified achievements
    quantified_score = int(min(15, num_count * 6))  # each numeric mention up to cap

    # 5. Hedging penalty
    hedging_penalty = int(min(10, hedge_count * 5))  # each hedging occurrence penalizes

    raw = length_score + action_score + leadership_score + quantified_score - hedging_penalty
    score = int(max(0, min(100, raw)))

    # Build explanations (strengths/weaknesses)
    strengths = []
    weaknesses = []
    if action_count > 0:
        strengths.append(f"Uses action verbs ({action_count}).")
    if lead_count > 0:
        strengths.append(f"Shows leadership/ownership ({lead_count}).")
    if num_count > 0:
        strengths.append(f"Provides quantified evidence ({num_count} numbers).")
    if 15 <= word_count <= 120:
        strengths.append("Answer length is appropriate.")

    if word_count < 15:
        weaknesses.append("Answer is short — expand with a concise example or result.")
    if action_count == 0:
        weaknesses.append("No clear action verbs — start bullets/sentences with strong verbs.")
    if lead_count == 0:
        weaknesses.append("No leadership/ownership signals detected — mention responsibility where relevant.")
    if num_count == 0:
        weaknesses.append("No quantified impact — add numbers (%) or metrics if possible.")
    if hedge_count > 0:
        weaknesses.append("Hedging words detected — prefer confident, outcome-focused language.")

    # Short actionable feedback
    feedback_lines = []
    feedback_lines.append(f"Score: {score}/100 — length:{length_score}, action:{action_score}, leadership:{leadership_score}, quantified:{quantified_score}, hedging_penalty:{hedging_penalty}.")
    if strengths:
        feedback_lines.append("Strengths: " + "; ".join(strengths))
    if weaknesses:
        feedback_lines.append("Opportunities: " + "; ".join(weaknesses[:3]))
    feedback = " ".join(feedback_lines)

    metrics = {
        "word_count": word_count,
        "action_verbs": action_count,
        "leadership_mentions": lead_count,
        "numeric_mentions": num_count,
        "hedging_count": hedge_count,
        "raw_components": {
            "length_score": length_score,
            "action_score": action_score,
            "leadership_score": leadership_score,
            "quantified_score": quantified_score,
            "hedging_penalty": hedging_penalty
        }
    }

    return {
        "score": score,
        "metrics": metrics,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": feedback
    }

# --- Router endpoints ---
@router.post("/start", response_model=StartResp)
def start_mock(req: StartReq):
    """
    Start a new mock interview session for a given role.
    Returns session_id and initial question.
    """
    role = (req.role or "").strip()
    if not role:
        raise HTTPException(status_code=400, detail="Role is required.")

    q = get_random_question(role)
    if not q:
        raise HTTPException(status_code=404, detail="No questions available for that role.")

    session_id = str(uuid.uuid4())
    SESSIONS[session_id] = {
        "role": role,
        "created_at": time.time(),
        "last_question": {"id": q.get("id"), "question": q.get("question")},
        "asked": [],
        "use_llm": bool(req.use_llm)
    }

    return {"status": "success", "data": {"session_id": session_id, "question": q.get("question"), "role": role}}


@router.post("/question", response_model=QuestionResp)
def get_question(payload: SessionIdReq):
    """
    Return the last question for the session or a fresh question if the session exists but no last_question.
    """
    sid = payload.session_id
    sess = SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    # If last_question exists, return it
    last = sess.get("last_question")
    if last and last.get("question"):
        return {"status": "success", "data": {"question_id": last.get("id"), "question": last.get("question")}}

    # Else fetch new question and attach
    q = get_random_question(sess.get("role"))
    sess["last_question"] = {"id": q.get("id"), "question": q.get("question")}
    return {"status": "success", "data": {"question_id": q.get("id"), "question": q.get("question")}}


@router.post("/answer")
def submit_answer(payload: AnswerReq):
    """
    Submit an answer to the current question. Returns deterministic evaluation and a next question.
    """
    sid = payload.session_id
    ans = payload.answer or ""
    sess = SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    last = sess.get("last_question")
    if not last or not last.get("id"):
        # fetch a question first
        q = get_random_question(sess.get("role"))
        sess["last_question"] = {"id": q.get("id"), "question": q.get("question")}
        last = sess["last_question"]

    # Evaluate deterministically
    eval_out = deterministic_evaluate(ans)

    # Record asked item
    record = {
        "id": last.get("id"),
        "question": last.get("question"),
        "answer": ans,
        "score": int(eval_out["score"]),
        "meta": eval_out["metrics"],
        "evaluated_at": time.time()
    }
    sess.setdefault("asked", []).append(record)

    # Prepare next question (do not reuse same question back-to-back)
    next_q = get_random_question(sess.get("role"))
    # Try a few times to avoid immediate repeat
    tries = 0
    while next_q.get("id") == last.get("id") and tries < 6:
        next_q = get_random_question(sess.get("role"))
        tries += 1
    sess["last_question"] = {"id": next_q.get("id"), "question": next_q.get("question")}

    return {
        "status": "success",
        "data": {
            "evaluation": {
                "score": eval_out["score"],
                "strengths": eval_out["strengths"],
                "weaknesses": eval_out["weaknesses"],
                "feedback": eval_out["feedback"],
                "metrics": eval_out["metrics"]
            },
            "next_question": {"question_id": next_q.get("id"), "question": next_q.get("question")},
            "session_id": sid,
            "history_count": len(sess.get("asked", []))
        }
    }

# small utility endpoint (optional) to inspect session (dev-only)
@router.get("/session/{session_id}")
def inspect_session(session_id: str):
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "success", "data": sess}
