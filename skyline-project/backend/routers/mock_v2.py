from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from backend.database import get_db
from backend import models, schemas
from backend.routers.profile import get_current_user
from backend.services.mock_engine import MockService  # <--- Import Service

router = APIRouter(prefix="/mock-v2", tags=["Mock Interview V2"])


class AnswerRequest(BaseModel):
    exchange_id: int
    user_answer: str


@router.post("/start-session", response_model=schemas.InterviewSessionRead)
def start_session(config: schemas.InterviewSetupRequest, db: Session = Depends(get_db)):
    user = get_current_user(db)
    
    # Create new session
    new_session = models.InterviewSession(
        user_id=user.id,
        target_role=config.target_role,
        difficulty=config.difficulty,
        interview_type=config.interview_type,
        total_questions=config.question_count,
        resume_id=config.resume_id,
        status="setup"  # Will switch to 'in_progress' when first question loads
    )
    
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.post("/{session_id}/next")
def get_next_question_endpoint(session_id: int, db: Session = Depends(get_db)):
    """
    Returns the next question for the given session.
    Delegates logic to MockService.get_next_question(session_id, db).
    """
    result = MockService.get_next_question(session_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Session not found")
    return result


@router.post("/submit-answer")
def submit_answer_endpoint(payload: AnswerRequest, db: Session = Depends(get_db)):
    """
    Submit an answer for an exchange (by exchange_id).
    Delegates scoring/evaluation to MockService.submit_answer(exchange_id, user_answer, db).
    """
    result = MockService.submit_answer(payload.exchange_id, payload.user_answer, db)
    if not result:
        raise HTTPException(status_code=404, detail="Question not found")
    return result


@router.post("/{session_id}/end")
def end_session_endpoint(session_id: int, db: Session = Depends(get_db)):
    """
    Finalize the session: compile transcript, ask the LLM for a full interview report,
    persist scores & feedback, and mark session completed.
    Delegates to MockService.end_session_and_score(session_id, db).
    """
    result = MockService.end_session_and_score(session_id, db)
    if not result:
        raise HTTPException(status_code=500, detail="Failed to generate report")
    return result


@router.get("/{session_id}/results")
def get_session_results(session_id: int, db: Session = Depends(get_db)):
    """
    Retrieve final session results (scores + feedback) after the session is completed.
    Delegates to MockService.get_results(session_id, db).
    """
    result = MockService.get_results(session_id, db)
    if not result:
        raise HTTPException(status_code=404, detail="Results not found or pending")
    return result
