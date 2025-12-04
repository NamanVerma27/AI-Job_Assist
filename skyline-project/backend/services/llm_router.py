"""
Lightweight LLM router for Mock V3.
Handles Questions, Evaluation, and Final Reports with Score Normalization.
"""

import logging
import re
import random
import json
from typing import Optional, Dict, Any

from backend.services import llm_engine
from backend.config import get_settings

try:
    from backend.services.mock.question_bank import get_random_question
except ImportError:
    def get_random_question(role, diff): return "Tell me about yourself."

logger = logging.getLogger(__name__)
settings = get_settings()

# ----------------------------
# Internal Helpers
# ----------------------------
def _clean_text(raw: str) -> str:
    if not raw: return ""
    # Strip markdown blocks if they wrap the whole content
    clean = raw.strip()
    if clean.startswith("```json"):
        clean = clean[7:]
    if clean.startswith("```"):
        clean = clean[3:]
    if clean.endswith("```"):
        clean = clean[:-3]
    return clean.strip()

def _normalize_dimensions(dims: Dict[str, Any]) -> Dict[str, int]:
    """Ensures scores are 0-100 integers."""
    cleaned = {}
    for key, val in dims.items():
        clean_key = key.replace("_", " ").title()
        try:
            score = float(val)
            if score <= 1.0: score *= 100
            elif score <= 10 and score > 0: score *= 10
            cleaned[clean_key] = int(min(100, max(0, score)))
        except:
            cleaned[clean_key] = 50
    return cleaned

def _simple_evaluate_answer(answer: str) -> Dict[str, Any]:
    """Fallback deterministic evaluator."""
    if not answer: return {"score": 0, "feedback": "No answer provided.", "metrics": {}}
    word_count = len(answer.split())
    score = min(100, int(word_count * 1.5))
    return {
        "score": score,
        "feedback": f"Deterministic Score: {score}/100 based on length ({word_count} words).",
        "suggested_rewrite": "AI unavailable. Ensure your answer follows the STAR method.",
        "strengths": [],
        "weaknesses": []
    }

def _parse_evaluation_text(raw: str) -> Optional[Dict[str, Any]]:
    """Robust parser: Tries JSON first, then Regex."""
    if not raw: return None
    
    # 1. Try Direct JSON Parse
    try:
        clean = _clean_text(raw)
        data = json.loads(clean)
        return {
            "score": int(data.get("score", 0)),
            "feedback": data.get("feedback", ""),
            "suggested_rewrite": data.get("suggested_rewrite") or data.get("improved_answer") or "",
            "strengths": data.get("strengths", []),
            "weaknesses": data.get("weaknesses", [])
        }
    except Exception:
        pass

    # 2. Fallback Regex
    text = _clean_text(raw)
    score_m = re.search(r"Score[:\s]*([0-9]{1,3})", text)
    score = int(score_m.group(1)) if score_m else 0
    feedback_m = re.search(r"Feedback[:\s]*\n?(.+)$", text, flags=re.DOTALL)
    feedback = feedback_m.group(1).strip() if feedback_m else text[:300]

    return {
        "score": score,
        "feedback": feedback,
        "suggested_rewrite": "AI rewrite parsing failed.",
        "strengths": [],
        "weaknesses": []
    }

# ----------------------------
# Public API
# ----------------------------

def ask_question(role: str = "general", difficulty: str = "Medium", type_: str = "Mixed", personality: str = "Professional") -> Dict[str, Any]:
    """Generates a question based on Type and Personality."""
    
    tone_map = {
        "Friendly": "Be supportive and polite.",
        "Professional": "Be objective and clear.",
        "Strict": "Be critical and concise. Demand high standards."
    }
    type_map = {
        "Technical": "Focus ONLY on technical concepts and coding.",
        "Behavioral": "Focus ONLY on soft skills and STAR method.",
        "System Design": "Focus on architecture and scalability.",
        "HR": "Focus on culture fit.",
        "Mixed": "Mix technical and behavioral."
    }
    
    system_msg = f"You are a {personality} interviewer for a '{role}' role. {tone_map.get(personality, '')} {type_map.get(type_, '')} Ask a {difficulty} level question."
    
    try:
        client = getattr(llm_engine, "client", None)
        model = getattr(llm_engine, "MODEL_NAME", "llama-3.1-8b-instant")
        if client:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": "Generate one interview question."}],
                temperature=0.7, max_tokens=150
            )
            text = _clean_text(resp.choices[0].message.content)
            if text: return {"ok": True, "text": text, "provider": "groq"}
    except Exception:
        pass

    q = get_random_question(role, difficulty)
    return {"ok": True, "text": q, "provider": "fallback"}


def evaluate_answer(question: str, answer: str, role: str = "general", type_: str = "Mixed", personality: str = "Professional") -> Dict[str, Any]:
    """
    Evaluates answer AGAINST the specific question.
    """
    system_msg = f"You are a {personality} interviewer for a {role} role."
    
    user_content = (
        f"Question: \"{question}\"\n"
        f"Candidate Answer: \"{answer}\"\n\n"
        "Task: Evaluate relevance, correctness, and depth.\n"
        "Return valid JSON:\n"
        "1. score (0-100)\n"
        "2. feedback (Did they answer THE question?)\n"
        "3. suggested_rewrite (Correct answer)\n"
        "4. strengths (list)\n"
        "5. weaknesses (list)"
    )

    try:
        client = getattr(llm_engine, "client", None)
        model = getattr(llm_engine, "MODEL_NAME", "llama-3.1-8b-instant")
        if client:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_content}],
                temperature=0.1, response_format={"type": "json_object"}
            )
            parsed = _parse_evaluation_text(resp.choices[0].message.content)
            if parsed: return {"ok": True, "provider": "groq", "evaluation": parsed}
    except Exception as e:
        logger.error(f"Eval failed: {e}")

    return {"ok": True, "provider": "fallback", "evaluation": _simple_evaluate_answer(answer)}

def generate_final_report(role: str, transcript: str) -> Dict[str, Any]:
    system_msg = f"You are a Senior Bar Raiser Interviewer for {role}."
    user_msg = (
        f"Analyze this transcript:\n\n{transcript}\n\n"
        "Return valid JSON with:\n"
        "1. dimensions: { \"Technical Proficiency\": 0-100, \"Communication\": 0-100, \"Problem Solving\": 0-100, \"Confidence\": 0-100 }\n"
        "2. feedback: { \n"
        "   quick_wins: [string, string], \n"
        "   strengths: [string], \n"
        "   weaknesses: [string] \n"
        "}"
    )

    try:
        client = getattr(llm_engine, "client", None)
        model = getattr(llm_engine, "MODEL_NAME", "llama-3.1-8b-instant")
        if client:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": system_msg}, {"role": "user", "content": user_msg}],
                temperature=0.2, response_format={"type": "json_object"}
            )
            raw = resp.choices[0].message.content
            clean = _clean_text(raw)
            data = json.loads(clean)
            data["dimensions"] = _normalize_dimensions(data.get("dimensions", {}))
            return data
            
    except Exception as e:
        logger.error(f"Report Gen Failed: {e}")

    return {
        "dimensions": {"Technical Proficiency": 50, "Communication": 50, "Problem Solving": 50},
        "feedback": {
            "quick_wins": ["Review the transcript."],
            "strengths": ["Completed session."],
            "weaknesses": ["AI analysis unavailable."]
        }
    }