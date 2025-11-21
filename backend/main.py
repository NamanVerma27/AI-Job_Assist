import os
import requests
import google.generativeai as genai
import io
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, ValidationError
from typing import Optional, List
from datetime import datetime, timezone
from dateutil.parser import parse
import PyPDF2
import docx

# --- All your existing configuration and models ---
# ... (This part is unchanged)
ADZUNA_APP_ID = "e0878b4a"
ADZUNA_APP_KEY = "1cd0cedb7c75a925aa696a54611ad4a4"
GEMINI_API_KEY = "YOUR_GOOGLE_AI_STUDIO_API_KEY"
genai.configure(api_key=GEMINI_API_KEY)
app = FastAPI()
origins = [ "http://localhost:3000", "http://localhost:5173" ]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
class Job(BaseModel): id: str; title: str; company: str; location: str; url: str; source: str; posted_date: datetime
class UserProfile(BaseModel): fullName: str; email: str; phone: Optional[str] = None; linkedin: Optional[str] = None; skills: str
def standardize_date(dt_str: str) -> datetime:
    dt = parse(dt_str)
    if dt.tzinfo is None: return dt.replace(tzinfo=timezone.utc)
    return dt

# --- All your existing job fetching functions ---
# ... (These are unchanged)
def fetch_arbeitnow_jobs(query: str) -> List[Job]:
    jobs = []
    response = requests.get(f"https://www.arbeitnow.com/api/job-board-api?search={query}")
    response.raise_for_status()
    for item in response.json().get("data", []):
        try:
            job = Job(id=item.get("slug"), title=item.get("title"), company=item.get("company_name"), location=item.get("location"), url=item.get("url"), source="ArbeitNow", posted_date=standardize_date(item.get("created_at")))
            jobs.append(job)
        except (ValidationError, TypeError, AttributeError): continue
    return jobs
def fetch_remotive_jobs(query: str) -> List[Job]:
    jobs = []
    response = requests.get(f"https://remotive.com/api/remote-jobs?search={query}")
    response.raise_for_status()
    for item in response.json().get("jobs", []):
        try:
            job = Job(id=str(item.get("id")), title=item.get("title"), company=item.get("company_name"), location=item.get("candidate_required_location", "Remote"), url=item.get("url"), source="Remotive", posted_date=standardize_date(item.get("publication_date")))
            jobs.append(job)
        except (ValidationError, TypeError, AttributeError): continue
    return jobs
def fetch_adzuna_jobs(query: str, location: str, company: str, days_old: int) -> List[Job]:
    jobs = []
    params = {'app_id': ADZUNA_APP_ID, 'app_key': ADZUNA_APP_KEY, 'results_per_page': 50, 'what': query, 'where': location or 'us', 'company': company, 'max_days_old': days_old if days_old > 0 else None }
    params = {k: v for k, v in params.items() if v is not None}
    response = requests.get("https://api.adzuna.com/v1/api/jobs/us/search/1", params=params)
    response.raise_for_status()
    for item in response.json().get("results", []):
        try:
            job = Job(id=item.get("id"), title=item.get("title"), company=item.get("company", {}).get("display_name"), location=item.get("location", {}).get("display_name"), url=item.get("redirect_url"), source="Adzuna", posted_date=standardize_date(item.get("created")))
            jobs.append(job)
        except (ValidationError, TypeError, AttributeError): continue
    return jobs

# --- All your existing main endpoints ---
# ... (These are unchanged)
@app.get("/")
def read_root(): return {"message": "Welcome to the Skyline API"}
@app.get("/jobs", response_model=List[Job])
def get_all_jobs(query: Optional[str] = None, location: Optional[str] = None, company: Optional[str] = None, days_old: Optional[int] = 0):
    all_jobs = []
    try:
        adzuna_jobs = fetch_adzuna_jobs(query, location, company, days_old)
        all_jobs.extend(adzuna_jobs)
        print(f"SUCCESS: Fetched {len(adzuna_jobs)} jobs from Adzuna.")
    except Exception as e:
        print(f"ERROR: Failed to fetch from Adzuna. Reason: {e}")
    if not location and not company:
        try:
            arbeitnow_jobs = fetch_arbeitnow_jobs(query)
            all_jobs.extend(arbeitnow_jobs)
            print(f"SUCCESS: Fetched {len(arbeitnow_jobs)} jobs from ArbeitNow.")
        except Exception as e:
            print(f"ERROR: Failed to fetch from ArbeitNow. Reason: {e}")
        try:
            remotive_jobs = fetch_remotive_jobs(query)
            all_jobs.extend(remotive_jobs)
            print(f"SUCCESS: Fetched {len(remotive_jobs)} jobs from Remotive.")
        except Exception as e:
            print(f"ERROR: Failed to fetch from Remotive. Reason: {e}")
    all_jobs.sort(key=lambda job: job.posted_date, reverse=True)
    return all_jobs
@app.post("/profile")
def save_user_profile(profile: UserProfile):
    print("Received User Profile:", profile.dict())
    return {"message": "Profile saved successfully!", "data": profile}

# --- NEW ENDPOINT FOR RESUME PARSING ---
@app.post("/upload-resume")
async def parse_resume(file: UploadFile = File(...)):
    content = ""
    try:
        file_bytes = await file.read()
        file_extension = os.path.splitext(file.filename)[1].lower()

        if file_extension == ".pdf":
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
            for page in pdf_reader.pages:
                content += page.extract_text()
        elif file_extension == ".docx":
            doc = docx.Document(io.BytesIO(file_bytes))
            for para in doc.paragraphs:
                content += para.text + "\n"
        else:
            return {"error": "Unsupported file type"}, 400
            
        return {"filename": file.filename, "content": content}
    except Exception as e:
        return {"error": str(e)}, 500