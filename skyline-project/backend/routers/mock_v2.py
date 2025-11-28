# backend/routers/mock_v2.py
"""
Mock Interview V2 router
- Start session:   POST /mock/start       { role, difficulty, question_count, resume_id? }
- Next question:   POST /mock/question    { session_id }
- Submit answer:   POST /mock/answer      { session_id, question_id, answer }
- End session:     POST /mock/end         { session_id }  (finalizes & returns results)
- Get results:     GET  /mock/results/{session_id}

Notes:
- This file keeps session state in an in-memory dict for fast local testing.
  Replace with persistent storage (DB/Redis) for production.
- Answer evaluation uses evaluate_answer_hybrid(...) from backend.services.mock_engine.
"""

import uuid
import time
import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException, Body

from pydantic import BaseModel

from backend.services.mock_engine import evaluate_answer_hybrid  # hybrid evaluator
from backend.services.text_cleaner import clean_text

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mock", tags=["Mock Interview"])

# ----------------------------
# Simple in-memory session store
# ----------------------------
# session structure:
# {
#   "id": session_id,
#   "role": "frontend",
#   "difficulty": "Medium",
#   "question_count": 5,
#   "resume_text": "...",
#   "questions": [ {question_id, question_text, asked:bool} ... ],
#   "history": [ {question_id, question_text, user_answer, evaluation, timestamp} ... ],
#   "created_at": ts,
#   "finished": False
# }
_SESSIONS: Dict[str, Dict] = {}

# ----------------------------
# Minimal question bank (fallback)
# ----------------------------
_DEFAULT_QUESTIONS = [
    "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
    "Describe how the browser rendering pipeline works and how you'd optimize rendering performance.",
    "How do you approach debugging a production issue that only happens intermittently?",
    "Explain event delegation and why it's useful in large web applications.",
    "Describe the differences between SQL and NoSQL databases and when you'd pick one over the other.",
    "How would you design a system for uploading and processing large files from users?",
    "Explain the lifecycle of a React component (or equivalent in your preferred frontend framework).",
    "Describe a time you had to refactor code — what was your process and the outcome?"
]

# Utility: generate question objects (IDs)
def _make_questions(role: str, count: int, difficulty: str) -> List[Dict]:
    # For now we pick from default questions heuristically.
    questions = []
    # rotate through default list if count > len(list)
    for i in range(count):
        q_text = _DEFAULT_QUESTIONS[i % len(_DEFAULT_QUESTIONS)]
        qid = str(uuid.uuid4())
        questions.append({"question_id": qid, "question_text": q_text, "asked": False, "current_index": i+1, "total_questions": count})
    return questions

# ----------------------------
# Request / Response models
# ----------------------------
class StartRequest(BaseModel):
    role: Optional[str] = "general"
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = 5
    resume_text: Optional[str] = None  # optional parsed resume contents

class SessionRef(BaseModel):
    session_id: str

class AnswerRequest(BaseModel):
    session_id: str
    question_id: str
    answer: str

# ----------------------------
# Helpers
# ----------------------------
def _get_session(session_id: str) -> Dict:
    s = _SESSIONS.get(session_id)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s

def _pick_next_question(session: Dict) -> Optional[Dict]:
    for q in session["questions"]:
        if not q.get("asked"):
            return q
    return None

def _summary_from_history(history: List[Dict]) -> Dict:
    # Build a lightweight summary: average score and counts
    if not history:
        return {"questions_answered": 0, "avg_score": 0}
    scores = [h.get("evaluation", {}).get("final_score", 0) for h in history if h.get("evaluation")]
    avg = int(round(sum(scores) / len(scores))) if scores else 0
    return {"questions_answered": len(history), "avg_score": avg, "scores": scores}

# ----------------------------
# Endpoints
# ----------------------------

@router.post("/start")
def start_session(req: StartRequest = Body(...)):
    # Basic validation & cleaning
    role = (req.role or "general").strip()
    difficulty = (req.difficulty or "Medium").strip()
    qcount = max(1, min(12, int(req.question_count or 5)))  # clamp
    resume_text = clean_text(req.resume_text or "", redact=False)

    session_id = str(uuid.uuid4())
    questions = _make_questions(role, qcount, difficulty)

    session = {
        "id": session_id,
        "role": role,
        "difficulty": difficulty,
        "question_count": qcount,
        "resume_text": resume_text,
        "questions": questions,
        "history": [],
        "created_at": time.time(),
        "finished": False
    }
    _SESSIONS[session_id] = session

    # return first question immediately for a smooth UX
    first_q = _pick_next_question(session)
    if first_q:
        # mark it asked (server-driven)
        first_q["asked"] = True
        resp = {"session_id": session_id, "question": first_q["question_text"], "question_id": first_q["question_id"], "role": role}
    else:
        resp = {"session_id": session_id, "question": None, "role": role}

    return {"status": "success", "data": resp}


@router.post("/question")
def get_question(ref: SessionRef = Body(...)):
    session = _get_session(ref.session_id)
    # find next unasked
    nxt = _pick_next_question(session)
    if not nxt:
        # no more questions
        return {"status": "completed", "data": {"message": "No more questions"}}
    # mark as asked and return
    nxt["asked"] = True
    return {"status": "success", "data": {"question_id": nxt["question_id"], "question": nxt["question_text"], "current_index": nxt.get("current_index", 0), "total_questions": nxt.get("total_questions", session["question_count"]) }}


@router.post("/answer")
def submit_answer(payload: AnswerRequest = Body(...)):
    session = _get_session(payload.session_id)
    qid = payload.question_id
    user_answer = (payload.answer or "").strip()

    # find question object
    qobj = next((q for q in session["questions"] if q["question_id"] == qid), None)
    if not qobj:
        raise HTTPException(status_code=404, detail="question not found in session")

    # Save a raw entry with timestamp (before evaluation) for audit
    entry = {
        "question_id": qid,
        "question_text": qobj.get("question_text"),
        "user_answer": user_answer,
        "timestamp": time.time(),
        "evaluation": None
    }

    # Run hybrid evaluation (deterministic + optional LLM). Keep it safe & bounded.
    try:
        eval_cfg = {
            "enable_llm": True,               # flip to False to force deterministic only
            "min_llm_confidence": 0.18,
            "min_word_count_for_llm": 6,
            "llm_timeout": 10
        }
        eval_result = evaluate_answer_hybrid(qobj.get("question_text"), user_answer, resume_text=session.get("resume_text"), config=eval_cfg)
    except Exception as e:
        logger.exception("Evaluation failed; falling back to deterministic summary: %s", e)
        # If evaluation failed catastrophically, provide a safe deterministic placeholder
        eval_result = {
            "final_method": "error",
            "final_score": 0,
            "deterministic": {},
            "llm": None
        }

    entry["evaluation"] = eval_result
    session["history"].append(entry)

    # Prepare next question or mark completed
    next_q = _pick_next_question(session)
    if next_q:
        next_q["asked"] = True
        next_payload = {"question_id": next_q["question_id"], "question": next_q["question_text"], "current_index": next_q.get("current_index", 0), "total_questions": next_q.get("total_questions", session["question_count"])}
    else:
        next_payload = {"status": "completed", "message": "No further questions. Call /mock/end to finish and get results."}

    # Response shape: includes evaluation + next question
    return {"status": "success", "data": {"evaluation": eval_result, "next_question": next_payload, "session_id": session["id"], "history_count": len(session["history"]) }}


@router.post("/end")
def end_session(ref: SessionRef = Body(...)):
    session = _get_session(ref.session_id)
    session["finished"] = True
    # Optionally run any final aggregation or post-processing here (e.g. generate rewrites via LLM)
    summary = _summary_from_history(session["history"])
    return {"status": "success", "data": {"session_id": session["id"], "summary": summary, "total_answered": len(session["history"]) }}


@router.get("/results/{session_id}")
def get_results(session_id: str):
    session = _get_session(session_id)
    # Build a sanitized results payload
    results = {
        "session_id": session["id"],
        "role": session["role"],
        "difficulty": session["difficulty"],
        "created_at": session["created_at"],
        "finished": session["finished"],
        "history": session["history"],
        "summary": _summary_from_history(session["history"])
    }
    return {"status": "success", "data": results}
