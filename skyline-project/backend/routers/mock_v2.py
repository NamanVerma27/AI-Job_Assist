# backend/routers/mock_v2.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationError
from typing import Optional, Dict, Any, List, Union
from uuid import uuid4
import logging
import threading
import traceback

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.mock_models import MockSession, MockInteraction

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/mock-v2", tags=["Mock V2"])

# ---- Try to import llm evaluator (LLM-first). If not available, we'll fallback to deterministic mock_engine ----
try:
    from backend.services.mock.llm_evaluator import ask_question as llm_ask_question, evaluate_answer as llm_evaluate_answer
    LLM_AVAILABLE = True
except Exception:
    LLM_AVAILABLE = False
    llm_ask_question = None
    llm_evaluate_answer = None

try:
    # deterministic fallback (existing rule-based evaluator)
    from backend.services.mock_engine import evaluate_answer as deterministic_evaluate_answer
    from backend.services.mock.question_bank import get_random_question as deterministic_get_question
    FALLBACK_AVAILABLE = True
except Exception:
    FALLBACK_AVAILABLE = False
    deterministic_evaluate_answer = None
    deterministic_get_question = None

# Simple in-memory store for session metadata (question_count, asked_count).
_sessions_meta_lock = threading.Lock()
_sessions_meta: Dict[str, Dict[str, Optional[int]]] = {}
# structure: { session_id: {"total": Optional[int], "asked": int} }


# ----- Request/Response models -----
class StartSessionReq(BaseModel):
    target_role: Optional[str] = "general"
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = None
    resume_id: Optional[int] = None


# Accept exchange_id as either str or int; we'll coerce to str internally to avoid 422
class SubmitAnswerReq(BaseModel):
    session_id: str
    answer: str
    exchange_id: Optional[Union[str, int]] = Field(default=None)


# ----- Helpers -----
def _get_session(db: Session, session_id: str) -> Optional[MockSession]:
    return db.query(MockSession).filter(MockSession.session_id == session_id).first()


def _create_interaction(db: Session, session: MockSession, question_text: Optional[str], answer_text: Optional[str] = None) -> MockInteraction:
    inter = MockInteraction(session_id_fk=session.id, question=question_text, answer=answer_text, feedback=None)
    db.add(inter)
    db.commit()
    db.refresh(inter)
    return inter


def _record_session_meta(session_id: str, total: Optional[int]):
    with _sessions_meta_lock:
        _sessions_meta[session_id] = {"total": total, "asked": 0}


def _inc_asked(session_id: str):
    with _sessions_meta_lock:
        meta = _sessions_meta.get(session_id)
        if not meta:
            _sessions_meta[session_id] = {"total": None, "asked": 1}
            return 1
        meta["asked"] = (meta.get("asked") or 0) + 1
        return meta["asked"]


def _get_meta(session_id: str) -> Dict[str, Optional[int]]:
    with _sessions_meta_lock:
        return _sessions_meta.get(session_id, {"total": None, "asked": 0})


def _should_finish(session_id: str) -> bool:
    meta = _get_meta(session_id)
    total = meta.get("total")
    asked = meta.get("asked", 0)
    if total is None:
        return False
    return asked >= total


def _ask_question_llm_or_fallback(role: str, difficulty: Optional[str]) -> Dict[str, Any]:
    """
    Return dict with keys: text (question text), provider (string)
    """
    # Try LLM first if available
    if LLM_AVAILABLE:
        try:
            res = llm_ask_question(role=role, difficulty=difficulty)
            if isinstance(res, dict) and res.get("text"):
                return {"text": res.get("text"), "provider": res.get("provider", "llm")}
        except Exception:
            logger.exception("LLM ask_question failed")

    # Fallback deterministic question bank
    try:
        if FALLBACK_AVAILABLE:
            q = deterministic_get_question(role=role, difficulty=difficulty)
            # deterministic_get_question might return either text or dict
            if isinstance(q, dict):
                return {"text": q.get("question") or q.get("text") or "Tell me about yourself.", "provider": "fallback"}
            return {"text": q or "Tell me about yourself.", "provider": "fallback"}
    except Exception:
        logger.exception("fallback question bank failed")

    # Ultimate safe default
    return {"text": "Tell me about yourself.", "provider": "fallback"}


def _evaluate_answer_llm_or_fallback(answer: str, role: str) -> Dict[str, Any]:
    """
    Return dict with keys:
      ok: bool
      evaluation: dict (score, feedback, metrics...)
      provider: str
    """
    if LLM_AVAILABLE:
        try:
            res = llm_evaluate_answer(answer=answer, role=role)
            # Expect a dict like {"ok": True, "evaluation": {...}, "provider": "llm"}
            if isinstance(res, dict) and res.get("ok", False):
                return {"ok": True, "evaluation": res.get("evaluation", {}), "provider": res.get("provider", "llm")}
        except Exception:
            logger.exception("LLM evaluate_answer failed")

    # Fallback deterministic evaluator
    if FALLBACK_AVAILABLE:
        try:
            ev = deterministic_evaluate_answer(answer, role)
            # deterministic_evaluate_answer expected to return a dict-like evaluation
            return {"ok": True, "evaluation": ev, "provider": "deterministic"}
        except Exception:
            logger.exception("deterministic evaluator failed")

    # Ultimate safe fallback
    return {"ok": False, "evaluation": {"score": 0, "feedback": "Evaluation unavailable."}, "provider": "none"}


# ----- Routes -----


@router.post("/start-session")
def start_session(payload: StartSessionReq, db: Session = Depends(get_db)):
    """
    Start a deterministic-first/LLM-fallback mock session.
    - Persists MockSession
    - Stores requested question_count in-memory (no DB change)
    - Returns first question
    """
    sid = str(uuid4())
    session = MockSession(session_id=sid, role=payload.target_role or "general", current_q=0, finished=False)
    db.add(session)
    db.commit()
    db.refresh(session)

    # Save meta for question count enforcement
    _record_session_meta(sid, payload.question_count)

    # Ask first question (LLM-first, fallback deterministic)
    q = _ask_question_llm_or_fallback(role=payload.target_role or "general", difficulty=payload.difficulty)

    try:
        _create_interaction(db, session, q["text"])
        session.current_q = 1
        db.add(session)
        db.commit()
        db.refresh(session)
        _inc_asked(sid)
    except Exception:
        logger.exception("failed to persist first question interaction")

    return {
        "status": "success",
        "data": {
            "session_id": sid,
            "question": q["text"],
            "role": payload.target_role or "general",
            "provider": q.get("provider")
        }
    }


@router.post("/{session_id}/next")
def next_question(session_id: str, db: Session = Depends(get_db)):
    """
    Return the next question for a session.
    If session has reached its requested question_count, return status: completed.
    """
    session = _get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    # Check if we should finish based on requested count
    if _should_finish(session_id):
        return {"status": "completed"}

    # Ask next question
    q = _ask_question_llm_or_fallback(role=session.role or "general", difficulty=None)

    try:
        inter = _create_interaction(db, session, q["text"])
        session.current_q = (session.current_q or 0) + 1
        db.add(session)
        db.commit()
        db.refresh(session)
        _inc_asked(session_id)
    except Exception:
        logger.exception("failed to persist next question")
        inter = None

    return {
        "question_id": str(inter.id) if inter else None,
        "question_text": q["text"],
        "current_index": session.current_q,
        "total_questions": _get_meta(session_id).get("total")
    }


@router.post("/submit-answer")
def submit_answer(req: SubmitAnswerReq, db: Session = Depends(get_db)):
    """
    Submit an answer for the latest question of the session.
    Flow:
     - find session
     - locate latest interaction without answer (or last interaction)
     - persist answer
     - evaluate via LLM-first then fallback deterministic
     - persist feedback
     - return evaluation + next_question (if any)
    """
    # Defensive validation + coercion
    try:
        # pydantic already validated presence of required fields; coerce exchange_id to str if present
        exchange_id_raw = req.exchange_id
        exchange_id = None
        if exchange_id_raw is not None:
            exchange_id = str(exchange_id_raw)
    except ValidationError as ve:
        logger.debug("validation error on submit-answer: %s", ve)
        raise HTTPException(status_code=400, detail="Invalid request payload")

    session = _get_session(db, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    # Find last interaction for this session (most recent)
    last_interaction = db.query(MockInteraction).filter(MockInteraction.session_id_fk == session.id).order_by(MockInteraction.created_at.desc()).first()
    if not last_interaction:
        # weird edge: create a placeholder
        last_interaction = _create_interaction(db, session, "Question placeholder")

    # If last_interaction already has answer, append a new interaction to store this answer
    try:
        if last_interaction.answer:
            inter = _create_interaction(db, session, None, answer_text=req.answer)
        else:
            inter = last_interaction
            inter.answer = req.answer
            db.add(inter)
            db.commit()
            db.refresh(inter)
    except Exception:
        logger.exception("failed to persist answer to DB")
        # return an explicit error payload the frontend can inspect
        raise HTTPException(status_code=500, detail="Failed to save answer")

    # Evaluate
    try:
        ev_res = _evaluate_answer_llm_or_fallback(answer=req.answer, role=session.role or "general")
        evaluation = ev_res.get("evaluation", {})
        provider = ev_res.get("provider", "none")
    except Exception:
        logger.exception("evaluation pipeline error")
        evaluation = {"score": 0, "feedback": "Evaluation failed."}
        provider = "none"

    # Persist feedback
    try:
        fb = evaluation.get("feedback") if isinstance(evaluation, dict) else str(evaluation)
        inter.feedback = fb
        db.add(inter)
        db.commit()
        db.refresh(inter)
    except Exception:
        logger.exception("failed to save feedback")

    # Decide whether to return next question or mark completed
    if _should_finish(req.session_id):
        # mark finished
        try:
            session.finished = True
            db.add(session)
            db.commit()
        except Exception:
            db.rollback()
        next_q = None
    else:
        # Ask next question
        q = _ask_question_llm_or_fallback(role=session.role or "general", difficulty=None)
        try:
            next_inter = _create_interaction(db, session, q["text"])
            session.current_q = (session.current_q or 0) + 1
            db.add(session)
            db.commit()
            db.refresh(session)
            _inc_asked(req.session_id)
            next_q = {"question_id": str(next_inter.id) if next_inter else None, "question": q["text"], "current_index": session.current_q, "total_questions": _get_meta(req.session_id).get("total")}
        except Exception:
            logger.exception("failed to persist next question after submit")
            next_q = {"question_id": None, "question": "", "current_index": session.current_q, "total_questions": _get_meta(req.session_id).get("total")}

    # Count answered history
    try:
        history_count = db.query(MockInteraction).filter(MockInteraction.session_id_fk == session.id, MockInteraction.answer != None).count()
    except Exception:
        logger.exception("failed counting history")
        history_count = 0

    return {
        "status": "success",
        "data": {
            "evaluation": evaluation,
            "next_question": next_q,
            "session_id": req.session_id,
            "history_count": history_count,
            "provider": provider
        }
    }


@router.post("/{session_id}/end")
def end_session(session_id: str, db: Session = Depends(get_db)):
    session = _get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")
    session.finished = True
    db.add(session)
    db.commit()
    # also remove meta
    with _sessions_meta_lock:
        _sessions_meta.pop(session_id, None)
    return {"status": "success"}


@router.get("/{session_id}/results")
def get_results(session_id: str, db: Session = Depends(get_db)):
    session = _get_session(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    interactions: List[MockInteraction] = db.query(MockInteraction).filter(MockInteraction.session_id_fk == session.id).order_by(MockInteraction.created_at.asc()).all()
    transcript = []
    scores = []
    for item in interactions:
        # attempt to parse "Score: <n>" from feedback
        score = None
        if item.feedback:
            import re
            m = re.search(r"Score[:\s]*([0-9]{1,3})", item.feedback)
            if m:
                try:
                    score = int(m.group(1))
                except Exception:
                    score = None
        if score is not None:
            scores.append(score)

        transcript.append({
            "question": item.question or "",
            "user_answer": item.answer or "",
            "feedback": item.feedback or ""
        })

    overall_score = sum(scores) / len(scores) if scores else None

    return {
        "status": "success",
        "data": {
            "overall_score": overall_score,
            "dimensions": {},
            "feedback": {
                "quick_wins": [],
                "strengths": [],
                "weaknesses": []
            },
            "transcript": transcript
        }
    }


# Debug route to view in-memory session meta (helpful during dev)
@router.get("/_debug/sessions")
def debug_sessions():
    with _sessions_meta_lock:
        return {"sessions_meta": dict(_sessions_meta)}
