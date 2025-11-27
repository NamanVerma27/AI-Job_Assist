# backend/routers/mock_v2.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.database import get_db
from backend import models, schemas
from backend.routers.profile import get_current_user
from backend.services.mock_engine import MockService

router = APIRouter(prefix="/mock-v2", tags=["Mock Interview V2"])


# -----------------------------
# Request Models
# -----------------------------
class AnswerRequest(BaseModel):
    exchange_id: int
    user_answer: str


# -----------------------------
# Start a new interview session
# -----------------------------
@router.post("/start-session", response_model=schemas.InterviewSessionRead)
def start_session(
    config: schemas.InterviewSetupRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    # Validate question count
    if config.question_count <= 0 or config.question_count > 50:
        raise HTTPException(status_code=400, detail="question_count must be between 1 and 50")

    new_session = models.InterviewSession(
        user_id=current_user.id,
        target_role=config.target_role,
        difficulty=config.difficulty,
        interview_type=config.interview_type,
        total_questions=config.question_count,
        resume_id=config.resume_id,
        status="setup",
    )

    db.add(new_session)
    db.commit()
    db.refresh(new_session)

    return new_session


# -----------------------------
# Fetch next question
# -----------------------------
@router.post("/{session_id}/next")
def get_next_question_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    result = MockService.get_next_question(session_id, db)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to fetch next question")
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "Internal error"))

    return result


# -----------------------------
# Submit answer
# -----------------------------
@router.post("/submit-answer")
def submit_answer_endpoint(
    payload: AnswerRequest,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    exchange = db.query(models.InterviewExchange).filter(models.InterviewExchange.id == payload.exchange_id).first()
    if not exchange:
        raise HTTPException(status_code=404, detail="Exchange not found")

    if exchange.session.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Forbidden access")

    result = MockService.submit_answer(payload.exchange_id, payload.user_answer, db)

    if not result:
        raise HTTPException(status_code=500, detail="Failed to submit answer")

    return result


# -----------------------------
# End session & Score the interview
# -----------------------------
@router.post("/{session_id}/end")
def end_session_endpoint(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    # Idempotent behavior: if completed, return results directly
    if session.status == "completed":
        result = MockService.get_results(session_id, db)
        return result

    result = MockService.end_session_and_score(session_id, db)

    if not result or result.get("status") == "error":
        raise HTTPException(
            status_code=500, detail=result.get("message", "AI scoring failed")
        )

    return result


# -----------------------------
# Fetch final results after session completion
# -----------------------------
@router.get("/{session_id}/results")
def get_session_results(
    session_id: int,
    db: Session = Depends(get_db),
    current_user: models.User = Depends(get_current_user),
):
    session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
    if not session or session.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Session not found")

    result = MockService.get_results(session_id, db)

    if not result:
        raise HTTPException(status_code=404, detail="Results not available yet")

    return result
