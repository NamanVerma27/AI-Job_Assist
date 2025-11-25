# backend/routers/ai_enhance.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Any, Dict
import json

from backend.services.llm_engine import LLMEngine

# Primary router (current production route)
router = APIRouter(prefix="/api/ai", tags=["AI Enhancement"])

# Alias router (backwards compatibility)
alias_router = APIRouter(prefix="/ai", tags=["AI Enhancement - Legacy Alias"])


class EnhanceRequest(BaseModel):
    report: Dict[str, Any]


def extract_missing_phrases(report: dict):
    try:
        raw_kw = report.get("raw", {}).get("keywords", {}).get("breakdown", {})
        if not raw_kw:
            return []
        phrases = []
        for tier in ("required", "preferred", "bonus"):
            block = raw_kw.get(tier, {})
            missing_list = block.get("missing", [])
            for item in missing_list:
                if isinstance(item, dict) and item.get("phrase"):
                    phrases.append(item["phrase"])
                elif isinstance(item, str):
                    phrases.append(item)
        return phrases[:10]
    except Exception:
        return []


def build_prompt(report: dict) -> str:
    compact = {
        "total_score": report.get("total_score"),
        "breakdown": report.get("breakdown"),
        "quick_wins": report.get("insights", {}).get("quick_wins", []),
        "overall_summary": report.get("insights", {}).get("overall_summary", ""),
        "role": report.get("role", {}),
        "top_missing_keywords": extract_missing_phrases(report),
    }

    schema_instruction = """
You are an elite Resume & ATS Expert.

Given the ATS analysis JSON, rewrite the quick wins into PREMIUM, CLEAR, ACTIONABLE suggestions.

⚠️ Output MUST be VALID JSON ONLY.
⚠️ NO markdown, NO comments, NO text outside JSON.

Return an array of objects in this EXACT schema:

[
  {
    "id": "short_snake_case_id",
    "title": "6 words max",
    "priority": "High" | "Medium" | "Low",
    "estimated_minutes": 5,
    "reason": "1 sentence explaining why this matters.",
    "recommendation": "1–2 sentences of actionable changes.",
    "before": "optional short snippet",
    "after": "optional improved rewrite"
  }
]

RULES:
- Make changes SPECIFIC to the resume & JD.
- Provide before/after only when relevant.
- Keep everything concise, sharp and helpful.
- DO NOT invent fake technologies or roles.
- Avoid generic advice — customize based on the ATS data.
"""

    return f"{schema_instruction}\n\nATS_JSON:\n{json.dumps(compact, indent=2, ensure_ascii=False)}"


def _perform_enhancement(report: dict):
    """
    Core logic: call the LLM and return parsed JSON or fallback to raw quick_wins.
    """
    prompt = build_prompt(report)
    try:
        raw_output = LLMEngine.generate_response(
            prompt,
            task_type="ats_enhance",
            role="ATS_Analyst"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM Engine failure: {str(e)}")

    cleaned = raw_output.replace("```json", "").replace("```", "").strip()
    try:
        parsed = json.loads(cleaned)
        return {"status": "success", "enhanced": parsed}
    except Exception:
        fallback = report.get("insights", {}).get("quick_wins", [])
        return {
            "status": "partial",
            "message": "Could not parse LLM JSON. Returning raw quick wins.",
            "enhanced": fallback
        }


@router.post("/enhance-ats")
def enhance_ats(req: EnhanceRequest):
    report = req.report
    if not report:
        raise HTTPException(status_code=400, detail="Missing ATS report.")
    return _perform_enhancement(report)


# Alias route for backwards compatibility: /ai/enhance-ats
@alias_router.post("/enhance-ats")
def enhance_ats_alias(req: EnhanceRequest):
    # Re-use identical logic
    report = req.report
    if not report:
        raise HTTPException(status_code=400, detail="Missing ATS report.")
    return _perform_enhancement(report)
