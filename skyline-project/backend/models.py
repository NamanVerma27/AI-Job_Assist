from sqlalchemy import Boolean, Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime
from backend.database import Base


# -----------------------------
# User Model
# -----------------------------
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    full_name = Column(String)
    phone = Column(String, nullable=True)
    linkedin = Column(String, nullable=True)
    location = Column(String, nullable=True)
    bio = Column(Text, nullable=True)
    skills = Column(Text, nullable=True)

    # Relationships
    experience = relationship("Experience", back_populates="owner", cascade="all, delete-orphan")
    education = relationship("Education", back_populates="owner", cascade="all, delete-orphan")
    projects = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    resumes = relationship("Resume", back_populates="owner", cascade="all, delete-orphan")

    # Recommended: reverse relationship for interviews
    interviews = relationship("InterviewSession", back_populates="owner", cascade="all, delete-orphan")


# -----------------------------
# Experience
# -----------------------------
class Experience(Base):
    __tablename__ = "experience"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String)
    company = Column(String)
    start_date = Column(String)
    end_date = Column(String, nullable=True)
    description = Column(Text, nullable=True)

    owner = relationship("User", back_populates="experience")


# -----------------------------
# Education
# -----------------------------
class Education(Base):
    __tablename__ = "education"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignForeignKey("users.id"))
    school = Column(String)
    degree = Column(String)
    year = Column(String)

    owner = relationship("User", back_populates="education")


# -----------------------------
# Project
# -----------------------------
class Project(Base):
    __tablename__ = "projects"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String)
    tech_stack = Column(String)
    description = Column(Text)
    link = Column(String, nullable=True)

    owner = relationship("User", back_populates="projects")


# -----------------------------
# Resume
# -----------------------------
class Resume(Base):
    __tablename__ = "resumes"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    filename = Column(String)
    filepath = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    parsing_status = Column(String, default="pending")
    primary_flag = Column(Boolean, default=False)
    note = Column(String(140), nullable=True)
    content = Column(Text, nullable=True)

    owner = relationship("User", back_populates="resumes")


# -----------------------------
# Interview Session
# -----------------------------
class InterviewSession(Base):
    __tablename__ = "interview_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))

    target_role = Column(String)
    difficulty = Column(String)
    interview_type = Column(String)
    total_questions = Column(Integer)
    resume_id = Column(Integer, ForeignKey("resumes.id"), nullable=True)

    status = Column(String, default="setup")
    current_question_index = Column(Integer, default=0)

    overall_score = Column(Integer, nullable=True)
    technical_score = Column(Integer, nullable=True)
    communication_score = Column(Integer, nullable=True)
    structure_score = Column(Integer, nullable=True)
    impact_score = Column(Integer, nullable=True)
    behavioral_score = Column(Integer, nullable=True)

    feedback_report = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("User", back_populates="interviews")
    resume = relationship("Resume")
    exchanges = relationship("InterviewExchange", back_populates="session", cascade="all, delete-orphan")


# -----------------------------
# Interview Exchange
# -----------------------------
class InterviewExchange(Base):
    __tablename__ = "interview_exchanges"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("interview_sessions.id"))

    question_text = Column(Text)
    question_order = Column(Integer)

    user_answer = Column(Text, nullable=True)

    # Atomic scoring fallback
    score_correctness = Column(Integer, nullable=True)
    score_clarity = Column(Integer, nullable=True)
    score_confidence = Column(Integer, nullable=True)

    ai_feedback = Column(Text, nullable=True)
    improved_answer = Column(Text, nullable=True)

    session = relationship("InterviewSession", back_populates="exchanges")
