# backend/services/llm_engine.py
"""
Deterministic rewrite for `rewrite_project`:
- For task_type == "rewrite_project" we DO NOT call the LLM.
- We synthesize a single past-tense action sentence from user input.
- All other tasks still use Groq/Gemini fallback as before.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Optional
from dotenv import load_dotenv
from openai import OpenAI
import google.generativeai as genai
from backend.config import get_settings

# Logging
logger = logging.getLogger("llm_engine")

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

settings = get_settings()

MODEL_NAME = "llama-3.1-8b-instant"

# Initialize Groq
client: Optional[OpenAI] = None
_groq_api_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
if _groq_api_key:
    try:
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=_groq_api_key)
        logger.info(f"LLM Engine: Connected to Groq ({MODEL_NAME})")
    except Exception as e:
        logger.error(f"Groq Init Error: {e}", exc_info=True)
        client = None

# Configure Gemini (non-fatal)
if getattr(settings, "GEMINI_API_KEY", None):
    try:
        genai.configure(api_key=getattr(settings, "GEMINI_API_KEY"))
    except Exception:
        logger.debug("genai configure failed or not available.", exc_info=True)


# =====================================================================
# Utility Helpers
# =====================================================================

def _extract_json_block(raw: str) -> Optional[dict]:
    """
    Safely extract a JSON object from any LLM output.
    Returns Python dict or None.
    """
    if not raw:
        return None

    try:
        text = raw.strip()
        start = text.find("{")
        end = text.rfind("}")

        if start == -1 or end == -1 or end <= start:
            return None

        block = text[start:end+1]
        return json.loads(block)

    except Exception as e:
        logger.error(f"JSON extraction failed: {e}", exc_info=True)
        return None


# =====================================================================
# LLM Engine Class
# =====================================================================

class LLMEngine:

    # ----------------------------
    # Deterministic synthesis
    # ----------------------------
    @staticmethod
    def _enforce_word_limit(text: str, max_words: int = 35) -> str:
        if not text:
            return ""
        parts = text.split()
        return " ".join(parts[:max_words]) if len(parts) > max_words else text

    @staticmethod
    def _synthesize_from_input(user_input: str) -> str:
        """
        Deterministic rewrite (no LLM call)
        """
        if not user_input or not user_input.strip():
            return "Built project."

        text = user_input.strip()
        lc = text.lower()

        verb_map = {
            "make": "Developed", "made": "Developed",
            "build": "Built", "built": "Built",
            "create": "Developed", "created": "Developed",
            "implement": "Implemented", "implemented": "Implemented",
            "write": "Implemented", "wrote": "Implemented",
            "fix": "Resolved", "fixed": "Resolved",
            "develop": "Developed", "developed": "Developed",
            "design": "Designed", "designed": "Designed",
            "deploy": "Deployed", "deployed": "Deployed",
            "engineer": "Engineered", "engineered": "Engineered",
            "launch": "Launched", "launched": "Launched",
            "automate": "Automated", "automated": "Automated",
        }

        # Remove leading pronouns
        lc = re.sub(r'^\s*(i am|i\'m|i|we|we\'re|we are)\s+', '', lc, flags=re.IGNORECASE).strip()

        # Capture first verb
        m = re.match(r'^(?P<v>[a-z]+)\s+(?P<rest>.+)$', lc)
        verb_word = None
        rest = lc
        if m:
            verb_word = m.group('v')
            rest = m.group('rest').strip()

        chosen_verb = None
        if verb_word and verb_word in verb_map:
            chosen_verb = verb_map[verb_word]
        else:
            for k in verb_map.keys():
                if re.search(r'\b' + re.escape(k) + r'\b', lc):
                    chosen_verb = verb_map[k]
                    break

        if not chosen_verb:
            chosen_verb = "Built"

        rest = re.sub(r'^\s*(a|an|the)\s+', '', rest, flags=re.IGNORECASE).strip()
        words = rest.split()
        if len(words) > 12:
            rest = " ".join(words[:12])

        # Capitalize rest
        if rest:
            rest = rest[0].upper() + rest[1:]
            if re.match(r'^[AEIOUaeiou]', rest):
                sentence = f"{chosen_verb} an {rest}."
            else:
                if re.match(r'^[A-Z]{2,}\b', rest):  # ACRONYM
                    sentence = f"{chosen_verb} {rest}."
                else:
                    sentence = f"{chosen_verb} a {rest}."
        else:
            sentence = f"{chosen_verb} project."

        sentence = re.sub(r'\s+', ' ', sentence).strip()
        sentence = sentence.rstrip(".") + "."

        sentence = LLMEngine._enforce_word_limit(sentence)
        if not sentence.endswith("."):
            sentence += "."

        return sentence

    # =====================================================================
    # PUBLIC API
    # =====================================================================

    @staticmethod
    def generate_response(prompt: str, task_type: str = "chat", role: str = "General") -> Optional[str]:
        """
        Unified LLM wrapper.
        Return None on any fatal error.
        """
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)

        # 1) Deterministic rewrite (NO LLM CALL)
        if task_type == "rewrite_project":
            return LLMEngine._synthesize_from_input(prompt)

        # 2) If no LLM keys available → return None
        if not client and not gemini_key:
            logger.error("No LLM backend available. (Groq/Gemini missing)")
            return None

        # Build system prompts
        if task_type == "refine_bio":
            system_msg = "You are a Resume Editor. Make the bio confident, polished. Max 40 words. No markdown."
        elif task_type == "improve_experience":
            system_msg = "Rewrite into a powerful bullet. Strong action verb. Add metrics if possible. No lists."
        elif task_type == "mock_interview":
            system_msg = f"You are an interviewer for a {role} role. Ask concise interview questions."
        elif task_type == "generate_question":
            system_msg = (
                "Generate ONE interview question based on role/difficulty. "
                "Professional, concise. Output ONLY the question."
            )
        elif task_type == "evaluate_answer":
            system_msg = (
                "Evaluate the candidate's answer in 2 sentences. "
                "Sentence 1: correctness. Sentence 2: one improvement. "
                "Be direct."
            )
        elif task_type == "generate_interview_report":
            system_msg = """
            You are a Senior Interviewer.
            Analyze the transcript and output STRICT JSON ONLY:
            {
                "scores": {
                    "technical": 0-100,
                    "communication": 0-100,
                    "structure": 0-100,
                    "impact": 0-100,
                    "behavioral": 0-100,
                    "overall": 0-100
                },
                "feedback": {
                    "strengths": ["..."],
                    "weaknesses": ["..."],
                    "quick_wins": [{"title": "...", "description": "..."}]
                }
            }
            """
        elif task_type == "resume":
            system_msg = "Resume Writer. Output JSON only."
        elif task_type == "reformat_description":
            system_msg = "Rewrite into one professional paragraph. No markdown. No bullet points."
        elif task_type == "improve_mock_answer":
            system_msg = (
                "Rewrite the candidate's answer into a perfect, structured (STAR) answer. "
                "3-4 concise sentences. Add metrics if missing."
            )
        else:
            system_msg = f"You are a helpful assistant. Role: {role}."

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Input: {prompt}\nOutput:"}
        ]

        # Try Groq
        raw_text = ""
        if client:
            try:
                resp = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=0.1,
                    max_tokens=300
                )
                raw_text = resp.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Groq LLM error: {e}", exc_info=True)

        # Fallback Gemini
        if not raw_text and gemini_key:
            try:
                model = genai.GenerativeModel("gemini-pro")
                full_prompt = f"{system_msg}\n\nInput: {prompt}\nOutput:"
                resp = model.generate_content(full_prompt)
                raw_text = getattr(resp, "text", "") or str(resp)
            except Exception as e:
                logger.error(f"Gemini LLM error: {e}", exc_info=True)

        if not raw_text:
            logger.error("LLM returned empty response.")
            return None

        # Cleanup formatting
        cleaned = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL)
        cleaned = cleaned.replace("`", "").replace("**", "").replace("*", "")
        cleaned = cleaned.strip()

        return cleaned or None

    # =====================================================================
    # Resume Generation
    # =====================================================================

    @staticmethod
    def generate_resume(profile_data: dict, job_description: str, style: str = "modern") -> Dict:
        """
        Resume generation with fallbacks.
        """
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)
        groq_env_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)

        if not gemini_key and not groq_env_key:
            return LLMEngine._get_mock_resume()

        system_msg = (
            "Resume Writer. Output ONLY valid JSON, no markdown fences."
        )

        prompt = f"""
REQUIRED STYLE: {style.upper()}

USER PROFILE:
{json.dumps(profile_data)}

JOB DESCRIPTION:
{job_description}

OUTPUT SCHEMA:
{{
  "resume_markdown": "# Name...",
  "suggestions": ["Tip 1", "Tip 2", "Tip 3"]
}}
"""

        raw_text = ""

        # Try Groq
        if client:
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                raw_text = response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Groq error in generate_resume: {e}", exc_info=True)

        # Try Gemini -> OpenAI fallback
        if not raw_text and gemini_key:
            try:
                gm = genai.GenerativeModel("gemini-pro")
                resp = gm.generate_content(f"{system_msg}\n\n{prompt}")
                raw_text = getattr(resp, "text", None) or str(resp)
            except Exception:
                logger.debug("Gemini fallback failed.", exc_info=True)

        if not raw_text:
            logger.error("No resume text; returning mock resume.")
            return LLMEngine._get_mock_resume()

        # Extract JSON
        data = _extract_json_block(raw_text)
        if data and isinstance(data, dict):
            return data

        logger.error("Failed to parse resume JSON; returning mock.")
        return LLMEngine._get_mock_resume()

    # ---------------------------------------------------------------------

    @staticmethod
    def _get_mock_resume() -> Dict:
        return {
            "resume_markdown": "# Mock Resume\n\nAI Service Unavailable.",
            "suggestions": [
                "Check API Keys (GROQ_API_KEY, GEMINI_API_KEY)",
                "Restart backend after setting keys"
            ],
        }
