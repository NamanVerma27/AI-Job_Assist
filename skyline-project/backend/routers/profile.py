from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from backend.database import get_db
from backend import models, schemas
from backend.config import get_settings

router = APIRouter(prefix="/profile", tags=["Profile V2"])
settings = get_settings()

# --- Helper: Get or Create Dummy User (Since we don't have Auth yet) ---
def get_current_user(db: Session):
    # For Phase 0, we use a single default user
    user = db.query(models.User).filter(models.User.email == "user@example.com").first()
    if not user:
        user = models.User(email="user@example.com", full_name="Demo User")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user

@router.get("/", response_model=schemas.UserProfileV2)
def get_profile(db: Session = Depends(get_db)):
    if not settings.PROFILE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="Profile V2 disabled")
    
    user = get_current_user(db)
    # Map DB model to Pydantic schema
    return schemas.UserProfileV2(
        full_name=user.full_name,
        email=user.email,
        phone=user.phone,
        linkedin=user.linkedin,
        location=user.location,
        bio=user.bio,
        skills=user.skills,
        experience=[schemas.ExperienceBase(title=e.title, company=e.company, start_date=e.start_date, end_date=e.end_date, description=e.description) for e in user.experience],
        education=[schemas.EducationBase(school=e.school, degree=e.degree, year=e.year) for e in user.education],
        projects=[schemas.ProjectBase(name=p.name, tech_stack=p.tech_stack, description=p.description, link=p.link) for p in user.projects]
    )

@router.post("/", response_model=schemas.UserProfileV2)
def update_profile(profile: schemas.UserProfileV2, db: Session = Depends(get_db)):
    if not settings.PROFILE_V2_ENABLED:
        raise HTTPException(status_code=503, detail="Profile V2 disabled")
        
    user = get_current_user(db)
    
    # Update Basic Fields
    user.full_name = profile.full_name
    user.phone = profile.phone
    user.linkedin = profile.linkedin
    user.location = profile.location
    user.bio = profile.bio
    user.skills = profile.skills
    
    # Update Relations (Simple Delete-All-Insert strategy for Phase 0)
    db.query(models.Experience).filter(models.Experience.user_id == user.id).delete()
    for exp in profile.experience:
        db.add(models.Experience(user_id=user.id, **exp.model_dump()))

    db.query(models.Education).filter(models.Education.user_id == user.id).delete()
    for edu in profile.education:
        db.add(models.Education(user_id=user.id, **edu.model_dump()))
        
    db.query(models.Project).filter(models.Project.user_id == user.id).delete()
    for proj in profile.projects:
        db.add(models.Project(user_id=user.id, **proj.model_dump()))

    db.commit()
    db.refresh(user)
    return get_profile(db)

# --- Resume Management Endpoints ---
@router.get("/resumes", response_model=List[schemas.ResumeMetadata])
def get_resumes(db: Session = Depends(get_db)):
    user = get_current_user(db)
    return user.resumes

@router.put("/resumes/{resume_id}/primary")
def set_primary_resume(resume_id: int, db: Session = Depends(get_db)):
    user = get_current_user(db)
    # Unset all
    db.query(models.Resume).filter(models.Resume.user_id == user.id).update({"primary_flag": False})
    # Set new
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id, models.Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.primary_flag = True
    db.commit()
    return {"status": "success"}

@router.put("/resumes/{resume_id}/note")
def update_resume_note(resume_id: int, note: str, db: Session = Depends(get_db)):
    user = get_current_user(db)
    resume = db.query(models.Resume).filter(models.Resume.id == resume_id, models.Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=404, detail="Resume not found")
    resume.note = note[:140] # Enforce constraint
    db.commit()
    return {"status": "success"}

@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    user = get_current_user(db)
    db.query(models.Resume).filter(models.Resume.id == resume_id, models.Resume.user_id == user.id).delete()
    db.commit()
    return {"status": "success"}