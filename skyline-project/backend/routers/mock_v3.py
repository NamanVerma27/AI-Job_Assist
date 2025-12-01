# backend/routers/mock_v3.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from uuid import uuid4
import logging
import inspect

from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models.mock_models import MockSession, MockInteraction
from backend.services import llm_router

# deterministic backup question supplier
from backend.services.mock.question_bank import get_random_question as deterministic_get_question

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mock-v3", tags=["Mock V3 (LLM-first)"])


# --------------------------------------------
# REQUEST MODELS
# --------------------------------------------
class StartReq(BaseModel):
    role: Optional[str] = "general"
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = None


class SubmitReq(BaseModel):
    session_id: str
    answer: str
    exchange_id: Optional[str] = None


# --------------------------------------------
# HELPERS
# --------------------------------------------
def _get_session_by_sid(db: Session, session_id: str) -> Optional[MockSession]:
    return (
        db.query(MockSession)
        .filter(MockSession.session_id == session_id)
        .first()
    )


def _create_interaction(db: Session, session: MockSession,
                        question_text: Optional[str],
                        answer_text: Optional[str] = None) -> MockInteraction:
    inter = MockInteraction(
        session_id_fk=session.id,
        question=question_text,
        answer=answer_text,
        feedback=None
    )
    db.add(inter)
    db.commit()
    db.refresh(inter)
    return inter


# --------------------------------------------
# DIFFICULTY-AWARE, SIGNATURE-SAFE QUESTION ASK
# --------------------------------------------
def _ask_question_llm_or_fallback(role: str, difficulty: Optional[str]) -> Dict[str, str]:

    # 1️⃣ TRY LLM FIRST (via llm_router)
    try:
        sig = inspect.signature(llm_router.ask_question)
        params = sig.parameters

        if "difficulty" in params:
            res = llm_router.ask_question(role=role, difficulty=difficulty)
        else:
            res = llm_router.ask_question(role=role)

        # usable output
        if isinstance(res, dict) and res.get("text"):
            return {"text": res["text"], "provider": res.get("provider", "llm")}

        if isinstance(res, str) and res.strip():
            return {"text": res.strip(), "provider": "llm"}

    except Exception as e:
        logger.exception("LLM ask_question failed: %s", e)

    # 2️⃣ FALLBACK TO DETERMINISTIC QUESTION BANK
    try:
        det = deterministic_get_question(role, difficulty)

        if isinstance(det, dict):
            t = (
                det.get("text")
                or det.get("question")
                or det.get("question_text")
                or det.get("q")
            )
            if t:
                return {"text": t, "provider": "fallback"}

            for v in det.values():
                if isinstance(v, str) and v.strip():
                    return {"text": v.strip(), "provider": "fallback"}

            return {"text": str(det), "provider": "fallback"}

        return {"text": str(det), "provider": "fallback"}

    except Exception as e:
        logger.exception("deterministic fallback failed: %s", e)

    # 3️⃣ SAFE LAST RESORT
    return {"text": "Tell me about yourself.", "provider": "fallback"}


# --------------------------------------------
# ROUTES
# --------------------------------------------

@router.post("/start")
def start_session(payload: StartReq, db: Session = Depends(get_db)):
    """
    Start a new LLM-first mock session, fallback-safe.
    """
    sid = str(uuid4())
    role = payload.role or "general"

    session = MockSession(
        session_id=sid,
        role=role,
        current_q=0,
        finished=False
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # ask first question
    q = _ask_question_llm_or_fallback(role, payload.difficulty)

    # persist
    try:
        _create_interaction(db, session, q["text"])
        session.current_q = 1
        db.commit()
        db.refresh(session)
    except Exception as e:
        logger.exception("failed to save first interaction: %s", e)

    return {
        "status": "success",
        "data": {
            "session_id": sid,
            "question": q["text"],
            "role": role,
            "provider": q["provider"]
        }
    }


@router.post("/submit-answer")
def submit_answer(req: SubmitReq, db: Session = Depends(get_db)):
    """
    LLM-first submit+evaluate+next-question.
    """
    session = _get_session_by_sid(db, req.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    # always force exchange_id to string to prevent 422 errors
    exchange_id = str(req.exchange_id) if req.exchange_id is not None else None

    # get last interaction
    last_inter = (
        db.query(MockInteraction)
        .filter(MockInteraction.session_id_fk == session.id)
        .order_by(MockInteraction.created_at.desc())
        .first()
    )

    if not last_inter:
        last_inter = _create_interaction(db, session, "Question placeholder")

    # store answer properly
    if last_inter.answer:
        inter = _create_interaction(db, session, None, req.answer)
    else:
        inter = last_inter
        inter.answer = req.answer
        db.commit()
        db.refresh(inter)

    # evaluate
    try:
        ev = llm_router.evaluate_answer(req.answer, role=session.role)
        evaluation = ev.get("evaluation", {})
        provider = ev.get("provider", "none")
    except Exception as e:
        logger.exception("LLM eval failed: %s", e)
        evaluation = {"score": 0, "feedback": "Evaluation unavailable."}
        provider = "fallback"

    # persist feedback
    try:
        fb = evaluation.get("feedback") if isinstance(evaluation, dict) else str(evaluation)
        inter.feedback = fb
        db.commit()
        db.refresh(inter)
    except Exception as e:
        logger.exception("failed to persist feedback: %s", e)

    # next question
    q = _ask_question_llm_or_fallback(session.role, None)

    next_inter = None
    if q["text"]:
        try:
            next_inter = _create_interaction(db, session, q["text"])
        except Exception as e:
            logger.exception("failed to create next interaction: %s", e)

    # update session index
    try:
        session.current_q = (session.current_q or 0) + 1
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()

    # count answered
    history_count = (
        db.query(MockInteraction)
        .filter(MockInteraction.session_id_fk == session.id,
                MockInteraction.answer != None)
        .count()
    )

    return {
        "status": "success",
        "data": {
            "evaluation": evaluation,
            "next_question": {
                "question_id": next_inter.id if next_inter else None,
                "question": q["text"],
                "current_index": session.current_q,
                "total_questions": None
            },
            "provider": provider,
            "session_id": req.session_id,
            "history_count": history_count
        }
    }


@router.post("/{session_id}/end")
def end_session(session_id: str, db: Session = Depends(get_db)):
    session = _get_session_by_sid(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    session.finished = True
    db.commit()

    return {"status": "success"}


@router.get("/{session_id}/results")
def get_results(session_id: str, db: Session = Depends(get_db)):
    """
    Aggregated results for V3 (same structure as V2).
    """
    session = _get_session_by_sid(db, session_id)
    if not session:
        raise HTTPException(status_code=404, detail="session not found")

    interactions = (
        db.query(MockInteraction)
        .filter(MockInteraction.session_id_fk == session.id)
        .order_by(MockInteraction.created_at.asc())
        .all()
    )

    transcript = []
    scores = []

    import re

    for it in interactions:
        if it.feedback:
            m = re.search(r"Score[:\s]*([0-9]{1,3})", it.feedback)
            if m:
                try:
                    scores.append(int(m.group(1)))
                except:
                    pass

        transcript.append({
            "question": it.question or "",
            "user_answer": it.answer or "",
            "feedback": it.feedback or ""
        })

    overall = sum(scores) / len(scores) if scores else None

    return {
        "status": "success",
        "data": {
            "overall_score": overall,
            "dimensions": {},
            "feedback": {
                "quick_wins": [],
                "strengths": [],
                "weaknesses": []
            },
            "transcript": transcript,
            "llm_summary": None
        }
    }
