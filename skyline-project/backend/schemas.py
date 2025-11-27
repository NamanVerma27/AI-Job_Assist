# backend/schemas.py
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


# --- Phase 0: New Nested Schemas ---

class ExperienceBase(BaseModel):
    title: str
    company: str
    start_date: str
    end_date: Optional[str] = None
    description: Optional[str] = None

    class Config:
        orm_mode = True


class EducationBase(BaseModel):
    school: str
    degree: str
    year: str

    class Config:
        orm_mode = True


class ProjectBase(BaseModel):
    name: str
    tech_stack: str
    description: str
    link: Optional[str] = None

    class Config:
        orm_mode = True


class ResumeMetadata(BaseModel):
    id: int
    filename: str
    upload_date: datetime
    parsing_status: str
    primary_flag: bool
    note: Optional[str] = None
    content: Optional[str] = None  # <--- NEW FIELD

    class Config:
        orm_mode = True


# --- Main Profile Schema ---

class UserProfileV2(BaseModel):
    full_name: str
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    skills: Optional[str] = None  # Keep as string for simple tag input

    experience: List[ExperienceBase] = Field(default_factory=list)
    education: List[EducationBase] = Field(default_factory=list)
    projects: List[ProjectBase] = Field(default_factory=list)

    class Config:
        orm_mode = True


# --- Legacy Schema (Keep for compatibility) ---

class Job(BaseModel):
    id: str
    title: str
    company: Optional[str] = "Unknown"
    location: Optional[str] = "Remote"
    url: str
    source: str
    posted_date: datetime

    class Config:
        orm_mode = True


class UserProfile(BaseModel):
    fullName: str  # Frontend uses camelCase currently
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    skills: Optional[str] = None

    class Config:
        extra = "allow"
        orm_mode = True


# --- Mock Interview V2 Schemas ---

class InterviewSetupRequest(BaseModel):
    target_role: str
    difficulty: str = "Medium"
    interview_type: str = "Mixed"
    question_count: int = 5
    resume_id: Optional[int] = None

    class Config:
        orm_mode = True


class InterviewExchangeRead(BaseModel):
    id: int
    question_text: Optional[str] = None
    question_order: Optional[int] = None
    user_answer: Optional[str] = None
    ai_feedback: Optional[str] = None
    improved_answer: Optional[str] = None
    score_correctness: Optional[int] = None
    score_clarity: Optional[int] = None
    score_confidence: Optional[int] = None

    class Config:
        orm_mode = True


class InterviewSessionRead(BaseModel):
    id: int
    user_id: Optional[int] = None
    target_role: Optional[str] = None
    difficulty: Optional[str] = None
    interview_type: Optional[str] = None
    status: Optional[str] = None
    current_question_index: Optional[int] = 0
    total_questions: Optional[int] = 0
    resume_id: Optional[int] = None
    created_at: Optional[datetime] = None

    # Final scores (may be null until completion)
    overall_score: Optional[int] = None
    technical_score: Optional[int] = None
    communication_score: Optional[int] = None
    structure_score: Optional[int] = None
    impact_score: Optional[int] = None
    behavioral_score: Optional[int] = None

    # Optional: small preview of feedback (keeps payload small)
    feedback_preview: Optional[dict] = None

    class Config:
        orm_mode = True
