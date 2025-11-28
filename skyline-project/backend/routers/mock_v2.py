from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend import models, schemas
from backend.routers.profile import get_current_user
from backend.services.mock_engine import MockService

router = APIRouter(prefix="/mock-v2", tags=["Mock Interview V2"])

class AnswerRequest(BaseModel):
    exchange_id: int
    user_answer: str

def _acquire_db():
    gen = get_db()
    try:
        return next(gen), gen
    except StopIteration:
        return None, None

def _close(gen):
    if gen:
        try: gen.close()
        except: pass

@router.post("/start-session", response_model=None)
def start_session(config: schemas.InterviewSetupRequest):
    db, gen = _acquire_db()
    if not db:
        raise HTTPException(500, "DB unavailable")
    try:
        user = get_current_user(db)

        session = models.InterviewSession(
            user_id=user.id,
            target_role=config.target_role,
            difficulty=config.difficulty,
            interview_type=config.interview_type,
            total_questions=config.question_count,
            resume_id=config.resume_id,
            status="setup",
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    finally:
        _close(gen)

@router.post("/{session_id}/next")
def get_next_question(session_id: int):
    db, gen = _acquire_db()
    if not db:
        raise HTTPException(500, "DB unavailable")

    try:
        user = get_current_user(db)
        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session or session.user_id != user.id:
            raise HTTPException(404, "Session not found")

        return MockService.get_next_question(session_id, db)
    finally:
        _close(gen)

@router.post("/submit-answer")
def submit_answer(payload: AnswerRequest):
    db, gen = _acquire_db()
    if not db:
        raise HTTPException(500, "DB unavailable")

    try:
        user = get_current_user(db)
        exchange = db.query(models.InterviewExchange).filter(models.InterviewExchange.id == payload.exchange_id).first()

        if not exchange:
            raise HTTPException(404, "Exchange not found")
        if exchange.session.user_id != user.id:
            raise HTTPException(403, "Forbidden")

        return MockService.submit_answer(payload.exchange_id, payload.user_answer, db)
    finally:
        _close(gen)

@router.post("/{session_id}/end")
def end_session(session_id: int):
    db, gen = _acquire_db()
    if not db:
        raise HTTPException(500, "DB unavailable")

    try:
        user = get_current_user(db)
        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()

        if not session or session.user_id != user.id:
            raise HTTPException(404, "Session not found")

        if session.status == "completed":
            return MockService.get_results(session_id, db)

        return MockService.end_session_and_score(session_id, db)
    finally:
        _close(gen)

@router.get("/{session_id}/results")
def get_results(session_id: int):
    db, gen = _acquire_db()
    if not db:
        raise HTTPException(500, "DB unavailable")

    try:
        user = get_current_user(db)

        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session or session.user_id != user.id:
            raise HTTPException(404, "Session not found")

        return MockService.get_results(session_id, db)
    finally:
        _close(gen)
