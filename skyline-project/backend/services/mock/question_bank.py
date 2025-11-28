# backend/services/mock/question_bank.py
import random

"""
Question Bank for Mock Interview V2
----------------------------------
• Questions grouped by ROLE
• Each role has difficulty tiers: Easy / Medium / Hard
• If a role or difficulty is missing → fallback to general pools
• Deterministic selection using random.choice
"""

# ---------------------------------------------------------
# CORE QUESTION BANK (extend anytime)
# ---------------------------------------------------------

QUESTION_BANK = {
    "general": {
        "Easy": [
            "Tell me about yourself.",
            "Why do you want this job?",
            "Describe a strength and a weakness.",
            "Tell me about a time you worked in a team.",
        ],
        "Medium": [
            "Describe a challenging situation and how you overcame it.",
            "Explain your workflow when dealing with tight deadlines.",
            "How do you handle disagreements at work?",
        ],
        "Hard": [
            "Explain your long-term career vision and how this role fits into it.",
            "Describe a major project you led end-to-end. What was the impact?",
        ],
    },

    "frontend": {
        "Easy": [
            "What is the difference between class and functional components in React?",
            "What is the DOM and how does the virtual DOM differ?",
            "Explain CSS specificity.",
        ],
        "Medium": [
            "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
            "Explain React reconciliation and how keys affect rendering.",
            "Describe how you optimize a React application for performance.",
        ],
        "Hard": [
            "Explain how React Fiber works internally.",
            "Describe the architecture decisions behind designing a scalable frontend system.",
            "How would you diagnose and fix layout thrashing in a large SPA?",
        ],
    },

    "backend": {
        "Easy": [
            "Explain REST vs SOAP.",
            "What is an API gateway?",
            "What is SQL vs NoSQL?",
        ],
        "Medium": [
            "Explain database indexing and when NOT to use an index.",
            "Describe caching strategies for high-scale systems.",
        ],
        "Hard": [
            "Explain microservices vs monolith — tradeoffs and architecture patterns.",
            "Describe how you'd scale a high-read, low-write API across regions.",
        ],
    },

    "fullstack": {
        "Easy": [
            "Explain the difference between frontend and backend responsibilities.",
            "What is CORS and why is it important?",
        ],
        "Medium": [
            "Describe how you'd design authentication for a fullstack app.",
        ],
        "Hard": [
            "Explain end-to-end system design for a social media feed.",
        ],
    },

    "data_science": {
        "Easy": [
            "Explain the difference between supervised and unsupervised learning.",
            "What is overfitting?",
        ],
        "Medium": [
            "Describe how you evaluate a machine learning model.",
            "Explain gradient descent in simple terms.",
        ],
        "Hard": [
            "Explain regularization and how L1 differs from L2.",
            "Design an ML pipeline for real-time fraud detection.",
        ],
    },
}

# ---------------------------------------------------------
# UTILITY FUNCTIONS
# ---------------------------------------------------------

def get_roles():
    """Return all available roles (including 'general')."""
    return list(QUESTION_BANK.keys())


def get_random_question(role: str, difficulty: str) -> str:
    """
    Return a random question for the role+difficulty.
    Falls back to:
       1. Same role but different difficulty
       2. General pool (same difficulty)
       3. General pool (any difficulty)
    """

    role = (role or "").lower().strip()
    difficulty = difficulty.capitalize().strip()

    # Normalize — if unknown role, fallback to general
    if role not in QUESTION_BANK:
        role = "general"

    # 1️⃣ Try exact match
    pool = QUESTION_BANK.get(role, {}).get(difficulty, [])
    if pool:
        return random.choice(pool)

    # 2️⃣ Try ANY difficulty within same role
    fallback_role = []
    for diff_pool in QUESTION_BANK.get(role, {}).values():
        fallback_role.extend(diff_pool)
    if fallback_role:
        return random.choice(fallback_role)

    # 3️⃣ Try general pool same difficulty
    pool = QUESTION_BANK.get("general", {}).get(difficulty, [])
    if pool:
        return random.choice(pool)

    # 4️⃣ Try general pool ANY difficulty
    general_all = []
    for diff_pool in QUESTION_BANK.get("general", {}).values():
        general_all.extend(diff_pool)
    if general_all:
        return random.choice(general_all)

    # 5️⃣ Worst-case fallback
    return "Tell me about yourself."


# ---------------------------------------------------------
# OPTIONAL — LOAD EXTERNAL YAML/JSON QUESTION BANK
# (Uncomment to use)
# ---------------------------------------------------------
"""
import json
import yaml
from pathlib import Path

def load_question_bank_from_file(path: str):
    ext = Path(path).suffix.lower()
    if ext == ".json":
        with open(path, "r") as f:
            QUESTION_BANK.update(json.load(f))
    elif ext in (".yaml", ".yml"):
        with open(path, "r") as f:
            QUESTION_BANK.update(yaml.safe_load(f))
    else:
        raise ValueError("Unsupported question bank format")
"""
