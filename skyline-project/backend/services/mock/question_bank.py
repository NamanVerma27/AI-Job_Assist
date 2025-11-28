# backend/services/mock/question_bank.py
import random
import uuid
from typing import Dict, List, Optional

# Simple sample question bank. Extend this with your real questions.
# Each item has an 'id' (uuid for the question item), 'role' and 'question' text.
_QUESTIONS = [
    {"id": str(uuid.uuid4()), "role": "frontend", "question": "Explain the difference between CSS Grid and Flexbox and when you'd use each."},
    {"id": str(uuid.uuid4()), "role": "frontend", "question": "How do you optimize rendering performance in a React application?"},
    {"id": str(uuid.uuid4()), "role": "backend", "question": "Describe how you would design a REST API for a note-taking application."},
    {"id": str(uuid.uuid4()), "role": "backend", "question": "Explain database indexing and a scenario where an index hurts performance."},
    {"id": str(uuid.uuid4()), "role": "data_scientist", "question": "How would you handle an imbalanced dataset when training a classifier?"},
    {"id": str(uuid.uuid4()), "role": "devops", "question": "Describe your approach to CI/CD pipelines for microservices."},
    # generic fallback
    {"id": str(uuid.uuid4()), "role": "general", "question": "Tell me about a challenging project you worked on and what you learned."},
]

def get_questions_for_role(role: str) -> List[Dict]:
    """Return list of questions matching the given role (case-insensitive)."""
    role_low = (role or "").lower()
    matches = [q for q in _QUESTIONS if q.get("role", "").lower() == role_low]
    if not matches:
        # If none for that role, return generic + random picks
        generics = [q for q in _QUESTIONS if q.get("role") == "general"]
        picks = [q for q in _QUESTIONS if q.get("role") != "general"]
        return generics + random.sample(picks, min(len(picks), 3))
    return matches

def get_random_question(role: str) -> Dict:
    """Return one random question dict for the role. Always returns a dict with 'id' and 'question'."""
    candidates = get_questions_for_role(role)
    return random.choice(candidates)

def get_question_by_id(qid: str) -> Optional[Dict]:
    for q in _QUESTIONS:
        if q.get("id") == qid:
            return q
    return None
