# backend/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.database import engine, Base

# Routers
from backend.routers import ai, jobs, resume, profile
from backend.routers import ai_enhance  # AI enhancement router + alias
from backend.routers import mock_v2     # Mock Interview V2 router

# Environment
from dotenv import load_dotenv
load_dotenv()

# Auto-create sqlite tables (safe for dev; for prod use migrations)
Base.metadata.create_all(bind=engine)

settings = get_settings()

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION
)

# -------------------------------------------------
# CORS (required for frontend)
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# -------------------------------------------------
# ROUTERS
# -------------------------------------------------

# Core Feature Modules
app.include_router(ai.router)
app.include_router(jobs.router)
app.include_router(resume.router)
app.include_router(profile.router)

# Mock Interview V2
app.include_router(mock_v2.router)

# ATS Enhancement routes (primary + legacy alias)
app.include_router(ai_enhance.router)       # e.g. /api/ai/enhance-ats
app.include_router(ai_enhance.alias_router) # legacy alias: /ai/enhance-ats

# -------------------------------------------------
# HEALTH CHECK
# -------------------------------------------------
@app.get("/")
def read_root():
    return {"message": "Skyline AI Backend is Running!"}

@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.ENV}

# -------------------------------------------------
# LOCAL DEV ENTRY
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
