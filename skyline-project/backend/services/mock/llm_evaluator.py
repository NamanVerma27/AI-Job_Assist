# backend/services/mock/llm_evaluator.py

import json
from backend.services.llm_engine import LLMEngine
from backend.services.text_cleaner import clean_text

"""
Hybrid LLM evaluation for mock interviews.
This module is OPTIONAL. Deterministic engine remains the default.
"""

def safe_json_parse(raw: str):
    """
    Attempts to extract the first valid JSON object from an LLM response.
    Returns {} if parsing fails.
    """
    if not raw:
        return {}

    text = raw.strip()
    # remove Markdown fences
    text = text.replace("```json", "").replace("```", "").strip()

    # Try direct load
    try:
        return json.loads(text)
    except:
        pass

    # try to salvage `{ ... }`
    try:
        start = text.index("{")
        end = text.rindex("}")
        snippet = text[start:end+1]
        return json.loads(snippet)
    except:
        return {}

def evaluate_answer_llm(role: str, question: str, answer: str) -> dict:
    """
    LLM-based evaluation with safe fallback.
    Returns deterministic structure:
    {
        "feedback": "...",
        "score": <0-100>,
        "reasoning": "...",
        "source": "llm" or "fallback"
    }
    """
    try:
        clean_ans = clean_text(answer or "", redact=False, max_chars=3000)

        prompt = f"""
You are an expert interviewer for the role "{role}".

Evaluate the following candidate's answer in a STRICT JSON format.

QUESTION:
{question}

CANDIDATE ANSWER:
{clean_ans}

Requirements for output:
- Provide a score from 0-100.
- Provide detailed feedback on correctness, clarity, depth, and alignment.
- Provide short reasoning for the score.
- JSON ONLY — no commentary.

Format:
{{
  "score": 85,
  "feedback": "Strong explanation with real examples. Missing mention of async data flow.",
  "reasoning": "Shows conceptual clarity but lacks implementation detail."
}}
        """

        raw = LLMEngine.generate_response(prompt, task_type="mock_interview_eval")
        data = safe_json_parse(raw)

        score = max(0, min(100, int(data.get("score", 0))))
        feedback = data.get("feedback", "") or "No feedback generated."
        reasoning = data.get("reasoning", "")

        return {
            "score": score,
            "feedback": feedback,
            "reasoning": reasoning,
            "source": "llm"
        }

    except Exception as e:
        # FAILSAFE
        return {
            "score": 0,
            "feedback": "AI evaluation unavailable — using deterministic fallback.",
            "reasoning": str(e),
            "source": "fallback"
        }
