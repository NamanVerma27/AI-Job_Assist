# backend/routers/mock_v3.py
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel
import uuid
from typing import Optional, Dict, Any

from backend.services.mock_engine_v3 import MockEngineV3

router = APIRouter(prefix="/mock-v3", tags=["Mock Interview V3"])

# single engine instance (in-memory; engine handles persistence)
engine = MockEngineV3()

# --- Request models ---
class StartRequest(BaseModel):
    role: str
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = 5
    resume_id: Optional[str] = None
    personality: Optional[str] = "neutral"  # new: personality selection

class AnswerRequest(BaseModel):
    session_id: str
    answer: str

class QuestionRequest(BaseModel):
    session_id: str

# --- Endpoints ---

@router.post("/start")
def start_session(req: StartRequest):
    """
    Start a new mock interview session.
    """
    sess = engine.start_session(
        role=req.role,
        difficulty=req.difficulty,
        question_count=int(req.question_count or 5),
        resume_id=req.resume_id,
        personality=req.personality
    )
    return {"status": "success", "data": sess}

@router.post("/question")
def get_question(body: QuestionRequest):
    """
    Get the next question for a running session.
    """
    q = engine.next_question(session_id=body.session_id)
    if q is None:
        raise HTTPException(status_code=404, detail="session not found or no more questions")
    return {"status": "success", "data": q}

@router.post("/answer")
def submit_answer(body: AnswerRequest):
    """
    Submit an answer and receive evaluation + optional improved answer.
    """
    res = engine.submit_answer(session_id=body.session_id, answer=body.answer)
    if res is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "success", "data": res}

@router.post("/end")
def end_session(session_id: str = Body(..., embed=True)):
    """
    Force-end a session and trigger final report generation.
    """
    report = engine.end_session(session_id=session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"status": "success", "data": report}

@router.get("/results")
def get_results(session_id: str):
    """
    Fetch final report if generated.
    """
    report = engine.get_report(session_id=session_id)
    if report is None:
        raise HTTPException(status_code=404, detail="report not found")
    return {"status": "success", "data": report}
