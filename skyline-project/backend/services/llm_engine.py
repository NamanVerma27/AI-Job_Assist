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

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

settings = get_settings()
logger = logging.getLogger(__name__)

MODEL_NAME = "llama-3.1-8b-instant"

# Initialize Groq client if available
client: Optional[OpenAI] = None
_groq_api_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
if _groq_api_key:
    try:
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=_groq_api_key)
        print(f"✅ LLM Engine: Connected to Groq ({MODEL_NAME})")
    except Exception as e:
        logger.error(f"Groq Init Error: {e}", exc_info=True)
        client = None

# Configure genai (non-fatal)
if getattr(settings, "GEMINI_API_KEY", None):
    try:
        genai.configure(api_key=getattr(settings, "GEMINI_API_KEY"))
    except Exception:
        logger.debug("genai configure failed or not available.", exc_info=True)


class LLMEngine:
    # ------------------------
    # Utilities for deterministic synthesis
    # ------------------------
    @staticmethod
    def _enforce_word_limit(text: str, max_words: int = 35) -> str:
        if not text:
            return ""
        parts = text.split()
        return " ".join(parts[:max_words]) if len(parts) > max_words else text

    @staticmethod
    def _synthesize_from_input(user_input: str) -> str:
        """
        Deterministic synthesis:
        - Map common weak verbs to strong past-tense verbs (made->Developed, built->Built, fixed->Resolved).
        - Remove leading pronouns.
        - Construct: "<Verb> a/an <short noun phrase>." or "<Verb> <ACRONYM/...>."
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

        # Remove leading pronouns like "i", "we"
        lc = re.sub(r'^\s*(i am|i\'m|i|we|we\'re|we are)\s+', '', lc, flags=re.IGNORECASE).strip()

        # Try to capture first verb and rest
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

        # Clean rest: remove leading articles
        rest = re.sub(r'^\s*(a|an|the)\s+', '', rest, flags=re.IGNORECASE).strip()
        rest_words = rest.split()
        if len(rest_words) > 12:
            rest = " ".join(rest_words[:12])

        # Capitalize rest appropriately
        if rest:
            rest = rest[0].upper() + rest[1:] if rest[0].isalpha() else rest
            # Choose article heuristics
            if re.match(r'^[AEIOUaeiou]', rest):
                sentence = f"{chosen_verb} an {rest}."
            else:
                if re.match(r'^[A-Z]{2,}\b', rest):
                    sentence = f"{chosen_verb} {rest}."
                else:
                    sentence = f"{chosen_verb} a {rest}."
        else:
            sentence = f"{chosen_verb} project."

        sentence = re.sub(r'\s+', ' ', sentence).strip()
        if not re.search(r'[\.!?]$', sentence):
            sentence = sentence.rstrip('.') + '.'

        # Enforce word limit (default 35 words)
        sentence = LLMEngine._enforce_word_limit(sentence, max_words=35)
        if not re.search(r'[\.!?]$', sentence):
            sentence = sentence.rstrip('.') + '.'
        return sentence

    # ------------------------
    # Public API
    # ------------------------
    @staticmethod
    def generate_response(prompt: str, task_type: str = "chat", role: str = "General") -> str:
        """
        If task_type == 'rewrite_project' -> deterministic synthesis (no LLM calls).
        Otherwise -> call LLM (Groq preferred) and return cleaned text.
        """
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)

        # If neither client present and task isn't rewrite_project, return demo
        if task_type != "rewrite_project" and not client and not gemini_key:
            return "Demo Mode: AI suggestions unavailable without key."

        # Deterministic short rewrite (guaranteed)
        if task_type == "rewrite_project":
            return LLMEngine._synthesize_from_input(prompt)

        # For other tasks, fallback to LLM call
        try:
            if task_type == "refine_bio":
                system_msg = "You are a Resume Editor. Reformat the bio to be professional , grammatical correct and confident. RULES: Max 40 words. NO markdown."
            elif task_type == "improve_experience":
                system_msg = "You are a Career Coach. Rewrite the input into a single powerful bullet point. RULES: Start with a strong Action Verb. Quantify results where possible. NO lists."
            elif task_type == "mock_interview":
                system_msg = f"You are a strict interviewer for a {role} role. Ask short, relevant questions."

            # --- MOCK INTERVIEW PROMPTS ---
            elif task_type == "generate_question":
                # Prompt expects: "Role: X, Difficulty: Y, Topic: Z"
                system_msg = (
                    "You are a strict Technical Interviewer. "
                    "Task: Generate ONE interview question based on the user's role. "
                    "Constraint: Keep it professional. No greetings. Just the question."
                )

            elif task_type == "evaluate_answer":
                # Prompt expects: "Question: Q, Answer: A"
                system_msg = (
                    "You are a Technical Interviewer evaluating a candidate. "
                    "Task: Provide 2 sentences of micro-feedback. "
                    "1. Is it correct? "
                    "2. What is one specific improvement? "
                    "Constraint: Be direct. Do not say 'Great job' unless it was perfect."
                )

            elif task_type == "generate_interview_report":
                system_msg = """
                You are a Senior Bar Raiser (Interviewer).
                Task: Analyze the interview transcript.
                Output: Strictly valid JSON.
                
                JSON Structure:
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
                        "strengths": ["point 1", "point 2"],
                        "weaknesses": ["point 1", "point 2"],
                        "quick_wins": [
                             {"title": "Fix X", "description": "Do Y"}
                        ]
                    }
                }
                """

            elif task_type == "resume":
                system_msg = "You are an expert Resume Writer. Output valid JSON only."
            elif task_type == "reformat_description":
                system_msg = (
                    "You are a professional technical writer. Reformat the USER'S DESCRIPTION into a single clean formatted paragraph. "
                    "Output ONLY the paragraph, nothing else especially no key points."
                )

            elif task_type == "improve_mock_answer":
                # Prompt expects: "Question: Q, User Answer: A"
                system_msg = """
                You are an Expert Interview Coach.
                Task: Rewrite the candidate's answer to be a "10/10" response.
                
                RULES:
                1. Keep the candidate's core experience if possible, but structure it better (STAR method).
                2. Add metrics/results if missing (use placeholders like [X]%).
                3. Keep it concise (max 3-4 sentences).
                4. Tone: Confident and Professional.
                """

            else:
                system_msg = f"You are a helpful assistant. Role: {role}."

            messages = [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": f"Input: {prompt}\nOutput:"}
            ]

            raw_text = ""

            # Try Groq
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
                    logger.error(f"Groq generate_response error: {e}", exc_info=True)
                    raw_text = ""

            # Fallback to genai (best-effort)
            if not raw_text and gemini_key:
                try:
                    model = genai.GenerativeModel("gemini-pro")
                    full_prompt = f"{system_msg}\n\nInput: {prompt}\nOutput:"
                    resp = model.generate_content(full_prompt)
                    raw_text = getattr(resp, "text", "") or str(resp)
                except Exception as e:
                    logger.error(f"genai generate_response error: {e}", exc_info=True)
                    raw_text = ""

            # Simple cleaning for UI
            if raw_text:
                # remove code fences and markdown, trim
                cleaned = re.sub(r"```.*?```", "", raw_text, flags=re.DOTALL)
                cleaned = cleaned.replace("`", "").replace("**", "").replace("*", "").strip()
                cleaned = re.sub(r"\r\n", "\n", cleaned)
                cleaned = re.sub(r"\n{2,}", "\n\n", cleaned)
                return cleaned.strip()

            return "AI Service did not return a response."

        except Exception as e:
            logger.error(f"LLM Error in generate_response: {e}", exc_info=True)
            return "AI Service Error."

    @staticmethod
    def generate_resume(profile_data: dict, job_description: str, style: str = "modern") -> Dict:
        """
        Resume generation (unchanged): Groq first, Gemini/OpenAI fallback, genai last.
        """
        gemini_key = getattr(settings, "GEMINI_API_KEY", None)
        groq_env_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)

        if not gemini_key and not groq_env_key:
            return LLMEngine._get_mock_resume()

        system_msg = (
            "You are an expert Resume Writer. Output strictly valid JSON. "
            "Do NOT include markdown formatting or code fences."
        )

        prompt = f"""
REQUIRED STYLE: {style.upper()}
- If 'MODERN': Concise, metric-heavy, active voice.
- If 'PROFESSIONAL': Formal, traditional structure.
- If 'CREATIVE': Engaging vocabulary, highlight personality.
- If 'ACADEMIC': Focus on research and detailed qualifications.

Task 1: Write a professional resume tailored to the JD.
Task 2: Provide 3 actionable tips.

USER PROFILE:
{json.dumps(profile_data)}

JOB DESCRIPTION:
{job_description}

OUTPUT SCHEMA (JSON ONLY):
{{
  "resume_markdown": "# Name...",
  "suggestions": ["Tip 1", "Tip 2", "Tip 3"]
}}
"""

        raw_text = ""

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
                raw_text = ""

        if not raw_text and gemini_key:
            try:
                gemini_model = getattr(settings, "GEMINI_MODEL", "gpt-4o-mini")
                temp_client = OpenAI(api_key=gemini_key)
                response = temp_client.chat.completions.create(
                    model=gemini_model,
                    messages=[
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=2000,
                )
                raw_text = response.choices[0].message.content or ""
            except Exception as e:
                logger.error(f"Gemini/OpenAI fallback error in generate_resume: {e}", exc_info=True)
                raw_text = ""

        if not raw_text and getattr(settings, "GEMINI_API_KEY", None):
            try:
                full_prompt = f"{system_msg}\n\n{prompt}"
                model = genai.GenerativeModel("gemini-pro")
                genai_resp = model.generate_content(full_prompt)
                raw_text = getattr(genai_resp, "text", None) or str(genai_resp)
            except Exception:
                logger.debug("genai fallback for resume failed or incompatible.", exc_info=True)

        if not raw_text:
            logger.error("No raw_text returned by any model in generate_resume; returning mock.")
            return LLMEngine._get_mock_resume()

        # Try parse JSON or extract {...} block
        clean_text = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE).strip()
        try:
            parsed = json.loads(clean_text)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            start = clean_text.find("{")
            end = clean_text.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    candidate = clean_text[start:end+1]
                    parsed = json.loads(candidate)
                    if isinstance(parsed, dict):
                        return parsed
                except json.JSONDecodeError:
                    logger.error("JSON parsing failed on extracted {...} block in generate_resume.", exc_info=True)

        logger.error("Failed to parse JSON from model output in generate_resume.")
        logger.debug(f"Model raw output (truncated): {clean_text[:4000]}")
        return LLMEngine._get_mock_resume()

    @staticmethod
    def _get_mock_resume() -> Dict:
        return {
            "resume_markdown": "# Mock Resume\n\nAI Service Unavailable.",
            "suggestions": ["Check API Keys (GROQ_API_KEY, GEMINI_API_KEY)", "Restart your backend after setting keys"]
        }
