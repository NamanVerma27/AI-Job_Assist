from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import get_settings
from backend.routers import ai, jobs, resume

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

@app.get("/health")
async def health_check():
    return {"status": "ok", "env": settings.ENV}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)