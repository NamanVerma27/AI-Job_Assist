from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class Job(BaseModel):
    id: str
    title: str
    company: Optional[str] = "Unknown"
    location: Optional[str] = "Remote"
    url: str
    source: str
    posted_date: datetime

class UserProfile(BaseModel):
    fullName: str
    email: str
    phone: Optional[str] = None
    linkedin: Optional[str] = None
    skills: str