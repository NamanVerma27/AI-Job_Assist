import io
import os
import PyPDF2
import docx
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import Dict, Any

# Import the new schema
from backend.schemas import UserProfile
from backend.services.scraper import extract_job_text
from backend.services.llm_engine import LLMEngine
from backend.services.ats_engine import get_ats_report  # <--- Added import
from backend.services.text_cleaner import clean_text  # NEW import

# Define the router
router = APIRouter(prefix="/resume", tags=["Resume"])

# --- Request Models ---
class ScrapeRequest(BaseModel):
    url: str

class GenerateRequest(BaseModel):
    profile: Dict[str, Any]
    job_description: str
    template_style: str = "modern"

class AtsRequest(BaseModel):  # <--- Added schema
    resume_text: str
    jd_text: str

# --- ENDPOINT 1: Upload & Parse Resume (PDF/DOCX) ---
@router.post("/upload-resume")
async def parse_resume(file: UploadFile = File(...)):
    content = ""
    try:
        file_bytes = await file.read()
        filename = file.filename.lower()

        if filename.endswith(".pdf"):
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    content += text

        elif filename.endswith(".docx"):
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                content += para.text + "\n"

        else:
            raise HTTPException(status_code=400, detail="Unsupported file type. Use PDF or DOCX.")

        # Clean the extracted text before returning (defensive normalization)
        cleaned = clean_text(content, redact=False)
        return {"filename": file.filename, "content": cleaned}

    except Exception as e:
        print(f"Error parsing resume: {e}")
        raise HTTPException(status_code=500, detail=f"Parsing error: {str(e)}")

# --- ENDPOINT 2: Scrape Job Description from URL ---
@router.post("/extract-job-desc")
async def extract_job_desc(request: ScrapeRequest):
    text = extract_job_text(request.url)
    if not text:
        return {
            "status": "partial_success",
            "message": "Could not auto-scrape. Please paste text manually.",
            "data": ""
        }
    return {"status": "success", "data": text}

# --- ENDPOINT 3: Generate Resume with AI ---
@router.post("/generate")
async def generate_resume_content(request: GenerateRequest):
    try:
        result = LLMEngine.generate_resume(
            request.profile,
            request.job_description,
            request.template_style
        )
        return {"status": "success", "data": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- ENDPOINT 4: Save User Profile ---
@router.post("/profile")
def save_user_profile(profile: UserProfile):
    """
    Saves user profile data (Currently just prints to console/logs).
    """
    print("Received User Profile:", profile.model_dump())
    return {"message": "Profile saved successfully!", "data": profile}

# --- ENDPOINT 4: ATS Score Checker ---
@router.post("/ats-score")
async def check_ats_score(request: AtsRequest):
    try:
        if not request.resume_text or not request.jd_text:
            raise HTTPException(status_code=400, detail="Both Resume and Job Description are required.")

        report = get_ats_report(request.resume_text, request.jd_text)
        return {"status": "success", "data": report}
    except Exception as e:
        print(f"ATS Error: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate ATS score.")
