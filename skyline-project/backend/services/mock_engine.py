# backend/services/mock_engine.py

"""
Deterministic mock interview engine (default).
Fast, stable, predictable.
"""

import textwrap

def evaluate_answer_det(role: str, question: str, answer: str) -> dict:
    """
    Basic scoring using heuristics:
    - length
    - keyword presence
    - clarity markers
    """
    if not answer or len(answer.strip()) < 10:
        return {
            "score": 10,
            "feedback": "Your answer is too short. Please explain with more detail.",
            "reasoning": "Very short answer.",
            "source": "deterministic"
        }

    score = 40

    good_keywords = ["experience", "project", "led", "implemented", "designed", "improved"]
    strong_hits = sum(1 for k in good_keywords if k in answer.lower())

    score += strong_hits * 10
    score = min(score, 95)

    feedback = "Good answer — but you can improve:\n"
    if strong_hits == 0:
        feedback += "- Add real examples from your experience.\n"
    else:
        feedback += "- Nice examples. Mention metrics or results.\n"

    if len(answer.split()) < 30:
        feedback += "- Try to elaborate more.\n"

    return {
        "score": score,
        "feedback": feedback.strip(),
        "reasoning": "Heuristic scoring",
        "source": "deterministic"
    }
