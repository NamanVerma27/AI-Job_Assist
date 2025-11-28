# backend/routers/mock_v2.py
"""
Compatibility router for Mock Interview endpoints.

Provides:
 - POST /mock/start and POST /mock-v2/start
 - POST /mock/question and POST /mock-v2/question
 - POST /mock/answer and POST /mock-v2/answer
 - POST /mock/end and POST /mock-v2/finish (aliases)
 - GET  /mock/{session_id}/results and /mock-v2/{session_id}/results

This is intentionally deterministic and lightweight so it works offline and
matches the deterministic evaluation flow (Option B).
"""

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
import time
import re

router = APIRouter()

# In-memory session store (reset on restart)
_SESSIONS: Dict[str, Dict[str, Any]] = {}

# Simple question bank (extendable)
_QUESTION_BANK = {
    "frontend": [
        "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
        "How do you optimize web page performance? Name 3 techniques.",
        "What are web accessibility (a11y) best practices you follow?"
    ],
    "backend": [
        "Explain database indexing and when to use it.",
        "How do you design a scalable REST API?",
        "Describe how you would debug memory leaks in a backend service."
    ],
    "general": [
        "Tell me about a time you led a project and what the outcome was.",
        "How do you prioritize tasks when everything is urgent?"
    ]
}

# --- Simple deterministic evaluator ---
def _evaluate_answer(answer: str) -> Dict[str, Any]:
    """
    Deterministic, reproducible scoring:
      - word_count: reward sensible length (10-60 words)
      - action_verbs: count of simple action verbs
      - leadership: count of leadership keywords
      - numbers: presence of digits (quantified)
      - hedging: penalty for hedging words
    Returns a dict with score 0-100 and details.
    """
    if not answer:
        return {"score": 0, "metrics": {}, "feedback": "No answer provided."}

    text = answer.strip()
    words = re.findall(r"\w+", text)
    word_count = len(words)

    ACTIONS = ["developed","created","designed","built","implemented","improved","optimized","led","managed","launched","initiated","resolved","mentored","owned","spearheaded"]
    LEADERSHIP = ["led","managed","supervised","owned","mentored","directed","coordinated"]
    HEDGES = ["might","could","maybe","possibly","may","sometimes","can be"]

    action_count = sum(1 for v in ACTIONS if re.search(r"\b" + re.escape(v) + r"\b", text, flags=re.IGNORECASE))
    lead_count = sum(1 for v in LEADERSHIP if re.search(r"\b" + re.escape(v) + r"\b", text, flags=re.IGNORECASE))
    nums = len(re.findall(r"\d+", text))
    hedge_count = sum(1 for v in HEDGES if re.search(r"\b" + re.escape(v) + r"\b", text, flags=re.IGNORECASE))

    # Length score (0..25)
    if word_count < 6:
        length_score = 5
    elif word_count <= 30:
        length_score = 20
    elif word_count <= 80:
        length_score = 15
    else:
        length_score = 10

    # Action verbs score (0..25)
    action_score = min(25, action_count * 8)  # each action verb ≈ 8 points up to cap

    # Leadership score (0..20)
    lead_score = min(20, lead_count * 7)

    # Quantified score (0..20)
    quant_score = 20 if nums >= 1 else 0

    # Hedging penalty (0..20)
    hedge_penalty = min(15, hedge_count * 7)

    raw = length_score + action_score + lead_score + quant_score - hedge_penalty
    total = max(0, min(100, int(raw)))

    strengths = []
    weaknesses = []

    if action_count:
        strengths.append(f"Uses action verbs ({action_count}).")
    if lead_count:
        strengths.append(f"Leadership signals ({lead_count}).")
    if nums:
        strengths.append(f"Quantified evidence ({nums} number(s)).")
    if word_count >= 6 and word_count <= 80:
        strengths.append("Answer length is appropriate.")

    if hedge_count:
        weaknesses.append(f"Hedging language detected ({hedge_count}). Use assertive phrasing.")
    if word_count < 6:
        weaknesses.append("Answer too short — expand with structure (STAR).")
    if word_count > 120:
        weaknesses.append("Answer too long — be more concise and focused.")

    feedback = f"Score: {total}/100 — length:{word_count}, action:{action_count}, leadership:{lead_count}, quantified:{nums}, hedging_penalty:{hedge_penalty}."

    return {
        "score": total,
        "metrics": {
            "word_count": word_count,
            "action_verbs": action_count,
            "leadership_mentions": lead_count,
            "numeric_mentions": nums,
            "hedging_count": hedge_count,
            "raw_components": {
                "length_score": length_score,
                "action_score": action_score,
                "leadership_score": lead_score,
                "quantified_score": quant_score,
                "hedging_penalty": hedge_penalty
            }
        },
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": feedback
    }

# --- Pydantic models for clarity ---
class StartRequest(BaseModel):
    role: Optional[str] = "general"
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = 3
    resume_id: Optional[str] = None

class SessionRef(BaseModel):
    session_id: str

class AnswerPayload(BaseModel):
    session_id: str
    answer: Optional[str] = None

# --- Helper functions ---
def _pick_question_for_role(role: str, idx: int) -> str:
    bank = _QUESTION_BANK.get(role) or _QUESTION_BANK.get("general")
    return bank[idx % len(bank)]

# --- Routes (aliasing both /mock and /mock-v2 paths) ---

# Start session
@router.post("/mock/start")
@router.post("/mock-v2/start")
def start_session(payload: StartRequest = Body(...)):
    sid = str(uuid.uuid4())
    role = (payload.role or "general").lower()
    qcount = max(1, payload.question_count or 3)
    session = {
        "session_id": sid,
        "role": role,
        "difficulty": payload.difficulty,
        "question_count": qcount,
        "created_at": time.time(),
        "index": 0,
        "history": [],  # list of {question_id, question_text, user_answer, evaluation}
        "completed": False
    }
    _SESSIONS[sid] = session

    first_q = _pick_question_for_role(role, 0)
    return {
        "status": "success",
        "data": {
            "session_id": sid,
            "question": first_q,
            "role": role
        }
    }

# Fetch current question (by session_id provided in body)
@router.post("/mock/question")
@router.post("/mock-v2/question")
def get_question(ref: SessionRef = Body(...)):
    sid = ref.session_id
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    if sess["completed"]:
        return {"status": "completed"}
    idx = sess["index"]
    q_text = _pick_question_for_role(sess["role"], idx)
    return {
        "status": "success",
        "data": {
            "question_id": f"q-{idx}",
            "question": q_text,
            "current_index": idx + 1,
            "total_questions": sess["question_count"]
        }
    }

# Submit answer
@router.post("/mock/answer")
@router.post("/mock-v2/answer")
def submit_answer(payload: AnswerPayload = Body(...)):
    sid = payload.session_id
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    if sess["completed"]:
        raise HTTPException(status_code=400, detail="session already completed")

    idx = sess["index"]
    q_text = _pick_question_for_role(sess["role"], idx)
    evaluation = _evaluate_answer(payload.answer or "")

    # store
    entry = {
        "question_id": f"q-{idx}",
        "question": q_text,
        "user_answer": payload.answer,
        "evaluation": evaluation
    }
    sess["history"].append(entry)

    # advance index
    sess["index"] += 1
    if sess["index"] >= sess["question_count"]:
        sess["completed"] = True
        next_q = None
    else:
        next_q = {
            "question_id": f"q-{sess['index']}",
            "question": _pick_question_for_role(sess["role"], sess["index"]),
            "current_index": sess["index"] + 1,
            "total_questions": sess["question_count"]
        }

    return {
        "status": "success",
        "data": {
            "evaluation": evaluation,
            "next_question": next_q,
            "session_id": sid,
            "history_count": len(sess["history"])
        }
    }

# End / finish aliases (previously returning 404)
@router.post("/mock/end")
@router.post("/mock-v2/finish")
@router.post("/mock-v2/end")
def end_session(ref: SessionRef = Body(...)):
    sid = ref.session_id
    sess = _SESSIONS.get(sid)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")
    sess["completed"] = True
    return {"status": "success", "message": "session marked finished", "session_id": sid}

# Results retrieval
@router.get("/mock/{session_id}/results")
@router.get("/mock-v2/{session_id}/results")
def get_results(session_id: str):
    sess = _SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(status_code=404, detail="session not found")

    # Build an aggregated report (simple deterministic aggregation)
    history = sess["history"]
    if not history:
        overall = 0
        dims = {}
        feedback = {}
    else:
        scores = [entry["evaluation"]["score"] for entry in history]
        overall = int(sum(scores) / len(scores))
        # dimensions: average of metrics
        dims = {}
        # average each metric across history if present
        metric_keys = ["word_count","action_verbs","leadership_mentions","numeric_mentions","hedging_count"]
        accum = {k: 0 for k in metric_keys}
        for entry in history:
            m = entry["evaluation"].get("metrics", {})
            for k in metric_keys:
                accum[k] += m.get(k, 0)
        dims = {k: int(accum[k]/len(history)) if len(history) else 0 for k in accum}

        # Provide friendly feedback blocks
        strengths = []
        weaknesses = []
        quick_wins = []
        for entry in history:
            ev = entry["evaluation"]
            strengths.extend(ev.get("strengths", []))
            weaknesses.extend(ev.get("weaknesses", []))
            # one-line quick win based on missing quantification
            if ev["metrics"].get("numeric_mentions", 0) == 0:
                quick_wins.append({"title": "Add numbers", "description": "Quantify impact (%, $ or counts) in your answer."})

        # dedupe and trim
        strengths = list(dict.fromkeys(strengths))[:6]
        weaknesses = list(dict.fromkeys(weaknesses))[:6]
        quick_wins = quick_wins[:6]

        feedback = {
            "strengths": strengths,
            "weaknesses": weaknesses,
            "summary": f"Average score across {len(history)} answers: {overall}/100",
            "quick_wins": quick_wins
        }

    # transcript
    transcript = []
    for e in history:
        transcript.append({
            "question": e["question"],
            "user_answer": e.get("user_answer"),
            "feedback": e["evaluation"].get("feedback"),
            # "improved_answer" not generated by deterministic engine; placeholder
            "improved_answer": e.get("user_answer") or ""
        })

    return {
        "status": "success",
        "data": {
            "session_id": session_id,
            "overall_score": overall,
            "dimensions": dims,
            "feedback": feedback,
            "transcript": transcript
        }
    }
