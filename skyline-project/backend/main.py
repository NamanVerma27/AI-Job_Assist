from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.database import engine, Base
# CHANGE 1: Import the profile router
from backend.routers import ai, jobs, resume, profile

# --- Load Environment ---
from dotenv import load_dotenv
load_dotenv()

# --- CHANGE 2: Auto-Create Database Tables ---
# This line tells SQLAlchemy to create the 'skyline.db' file 
# and build the tables defined in backend/models.py
Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION)

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(ai.router)
app.include_router(jobs.router)
app.include_router(resume.router)
# CHANGE 3: Register the profile router
app.include_router(profile.router)

@app.get("/")
def read_root():
    return {"message": "Skyline AI Backend is Running!"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.ENV}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)