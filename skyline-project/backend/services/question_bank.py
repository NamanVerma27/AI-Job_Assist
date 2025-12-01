# backend/services/question_bank.py
"""
Deterministic fallback question bank.
Simple role/difficulty keyed bank.
"""

from typing import Optional
import random

_BANK = {
    "frontend": {
        "Easy": [
            "What is the difference between class and id in CSS?",
            "Explain event delegation in JavaScript."
        ],
        "Medium": [
            "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
            "How do you optimize rendering performance in React?"
        ],
        "Hard": [
            "Describe how the virtual DOM works and how reconciliation is performed.",
            "Walk me through implementing a progressive web app (PWA) with offline support."
        ]
    },
    "backend": {
        "Easy": [
            "What is a RESTful API?",
            "Explain database normalization."
        ],
        "Medium": [
            "How does a database transaction work?",
            "Explain how you would design an authentication system."
        ],
        "Hard": [
            "Describe how to scale a write-heavy relational database.",
            "Explain CAP theorem and trade-offs in distributed systems."
        ]
    },
    "general": {
        "Easy": ["Tell me about a project you are proud of."],
        "Medium": ["Describe a situation where you had to handle conflict in a team."],
        "Hard": ["Describe a time you had to pivot a project under pressure; what did you learn?"]
    }
}

class QuestionBank:
    def __init__(self):
        self.bank = _BANK

    def get_question(self, role: str = "general", difficulty: str = "Medium") -> str:
        role_key = role.lower()
        if role_key not in self.bank:
            role_key = "general"
        choices = self.bank.get(role_key, {}).get(difficulty, [])
        if not choices:
            # fallback pick from general medium
            choices = self.bank.get("general", {}).get("Medium", ["Tell me about yourself."])
        return random.choice(choices)
