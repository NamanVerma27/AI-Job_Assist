"""
ATS Engine v2 — Orchestrator
----------------------------

This file integrates all ATS modules and produces the final structured output.

Pipeline:
1. Structure Analysis
2. Keyword Scoring
3. Semantic Similarity
4. Readability Analysis
5. Tone & Impact
6. Role Detection
7. Insight Generation
8. Weighted Final Score

Output Format:
{
  "total_score": 84,
  "scores": {
      "structure": 70,
      "keywords": 61,
      "semantics": 82,
      "readability": 74,
      "tone": 69
  },
  "role": {...},
  "insights": {...},
  "raw": {
      ... full outputs from every module ...
  }
}

This is what your frontend will use for ATS v2.
"""

from typing import Dict
from .ats_config import ATS_CONFIG
from .structure_analyzer import analyze_structure
from .keyword_engine import analyze_keywords
from .semantic_engine import compute_semantic_similarity
from .readability import analyze_readability
from .tone_analyzer import analyze_tone
from .role_detector import detect_role
from .insights import generate_insights


def run_ats_v2(resume_text: str, jd_text: str) -> Dict:
    """
    Main entrypoint for ATS v2.

    This can be mapped to:
    POST /resume/ats-score-v2
    """

    # -------------------------
    # Run all modules
    # -------------------------

    structure_result = analyze_structure(resume_text) if ATS_CONFIG["enable_structure"] else {}
    keyword_result = analyze_keywords(resume_text, jd_text) if ATS_CONFIG["enable_keywords"] else {}
    semantic_result = compute_semantic_similarity(resume_text, jd_text) if ATS_CONFIG["enable_semantics"] else {}
    readability_result = analyze_readability(resume_text) if ATS_CONFIG["enable_readability"] else {}
    tone_result = analyze_tone(resume_text) if ATS_CONFIG["enable_tone"] else {}
    role_result = detect_role(resume_text) if ATS_CONFIG["enable_role_detection"] else {}

    # -------------------------
    # Weighted Final Score
    # -------------------------

    weights = ATS_CONFIG["weights"]

    # Each module should output a normalized score 0–100
    struct_s = structure_result.get("structure_score", 0)
    key_s = keyword_result.get("keyword_score", 0)
    sem_s = semantic_result.get("semantic_score", 0)
    read_s = readability_result.get("readability_score", 0)
    tone_s = tone_result.get("tone_score", 0)

    final_score = (
        struct_s * weights["structure"] +
        key_s * weights["keywords"] +
        sem_s * weights["semantics"] +
        read_s * weights["readability"] +
        tone_s * weights["tone"]
    )

    final_score = int(round(final_score))

    # -------------------------
    # Insights
    # -------------------------
    insights_input = {
        "structure": structure_result,
        "keywords": keyword_result,
        "semantics": semantic_result,
        "readability": readability_result,
        "tone": tone_result,
        "role": role_result
    }

    insights = generate_insights(insights_input) if ATS_CONFIG["enable_insights"] else {}

    # -------------------------
    # Final Output
    # -------------------------

    return {
        "total_score": final_score,
        "scores": {
            "structure": struct_s,
            "keywords": key_s,
            "semantics": sem_s,
            "readability": read_s,
            "tone": tone_s
        },
        "role": role_result,
        "insights": insights,
        "raw": insights_input
    }
