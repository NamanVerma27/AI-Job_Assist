from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import io
import os
import pathlib
import PyPDF2
import docx

from backend.database import get_db
from backend import models, schemas
from backend.config import get_settings

# New helper import: text cleaning utility
try:
    from backend.services.text_cleaner import clean_text
except Exception:
    # Fallback if text_cleaner not present (should not happen in normal flow)
    def clean_text(x, redact=False):
        return x or ""

# Optional OCR support (used only when selectable text extraction is insufficient)
try:
    from pdf2image import convert_from_bytes
    import pytesseract
    OCR_AVAILABLE = True
except Exception:
    OCR_AVAILABLE = False

router = APIRouter(prefix="/profile", tags=["Profile V2"])
settings = get_settings()

# --- Helper: Get or Create Dummy User (Since we don't have Auth yet) ---
# NOTE: make this a proper FastAPI dependency so other routers can use:
#   Depends(get_current_user)
# It also remains callable directly with a DB session.
def get_current_user(db: Session = Depends(get_db)):
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

@router.post("/resumes", response_model=schemas.ResumeMetadata)
async def add_resume(file: UploadFile = File(...), db: Session = Depends(get_db)):
    """
    Upload endpoint enhancements:
    - Attempts to extract text from PDF/DOCX using PyPDF2/docx.
    - If selectable text is insufficient and OCR libs are present, attempts OCR via pytesseract.
    - Cleans text with clean_text before saving into DB.
    - Saves uploaded file bytes to `backend/uploads/` (creates dir if missing).
    - Sets parsing_status: "parsed", "parsed_via_ocr", or "failed".
    """
    user = get_current_user(db)

    # Ensure uploads dir exists
    uploads_dir = pathlib.Path(__file__).resolve().parents[1] / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)

    content = ""
    parsing_status = "pending"
    saved_filepath = ""

    try:
        file_bytes = await file.read()
        filename = file.filename or "uploaded_resume"
        filename_lower = filename.lower()

        # Save the raw uploaded file to disk (safe default: overwrite if same name)
        safe_filename = filename.replace(" ", "_")
        saved_path = uploads_dir / safe_filename
        with open(saved_path, "wb") as f:
            f.write(file_bytes)
        saved_filepath = str(saved_path)

        # 1) Try PyPDF2 for PDF text extraction (fast)
        if filename_lower.endswith(".pdf"):
            try:
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                pages = []
                for page in pdf_reader.pages:
                    try:
                        text = page.extract_text() or ""
                        pages.append(text)
                    except Exception:
                        # continue on page extraction failure
                        continue
                content = "\n\n".join(pages).strip()
            except Exception:
                content = ""

            # 2) If content too short and OCR available, perform OCR
            if (not content or len(content.strip()) < 200) and OCR_AVAILABLE:
                try:
                    images = convert_from_bytes(file_bytes, dpi=200, fmt="jpeg")
                    ocr_pages = []
                    for img in images:
                        try:
                            txt = pytesseract.image_to_string(img, lang='eng')
                        except Exception:
                            txt = ""
                        ocr_pages.append(txt)
                    ocr_text = "\n\n".join(ocr_pages).strip()
                    # Prefer OCR text if it's longer/more complete
                    if ocr_text and len(ocr_text) > len(content or ""):
                        content = ocr_text
                        parsing_status = "parsed_via_ocr"
                except Exception:
                    # If OCR fails, leave content as-is (may be empty)
                    parsing_status = parsing_status or "failed"
            else:
                # if PyPDF2 got reasonable text
                if content and len(content.strip()) >= 200:
                    parsing_status = "parsed"

        elif filename_lower.endswith(".docx"):
            try:
                doc = docx.Document(io.BytesIO(file_bytes))
                paras = [para.text for para in doc.paragraphs]
                content = "\n".join(paras).strip()
                if content and len(content) >= 50:
                    parsing_status = "parsed"
            except Exception:
                content = ""
                parsing_status = "failed"
        else:
            # unsupported file types
            content = ""
            parsing_status = "failed"

    except Exception as e:
        # Log server-side for debugging
        print(f"[add_resume] Parsing error: {e}")
        content = ""
        parsing_status = "failed"

    # Final cleaning step (always run, even on OCR output)
    try:
        cleaned = clean_text(content, redact=False)
    except Exception:
        # Fallback: keep raw content if clean_text utility missing/throws
        cleaned = content or ""

    # Sanity check & final parsing_status adjustments
    if not cleaned or len(cleaned.strip()) < 20:
        parsing_status = "failed"
    elif parsing_status == "pending":
        parsing_status = "parsed"

    # 2. Save to Database
    new_resume = models.Resume(
        user_id=user.id,
        filename=filename,
        filepath=saved_filepath or f"/uploads/{filename}",
        parsing_status=parsing_status,
        content=cleaned  # Save the extracted + cleaned text for downstream modules
    )
    db.add(new_resume)
    db.commit()
    db.refresh(new_resume)

    return new_resume

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
    resume.note = note[:140]  # Enforce constraint
    db.commit()
    return {"status": "success"}

@router.delete("/resumes/{resume_id}")
def delete_resume(resume_id: int, db: Session = Depends(get_db)):
    user = get_current_user(db)
    db.query(models.Resume).filter(models.Resume.id == resume_id, models.Resume.user_id == user.id).delete()
    db.commit()
    return {"status": "success"}
