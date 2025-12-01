# backend/services/llm_engine.py
"""
LLM Engine wrapper (Groq primary, Gemini fallback) with deterministic rewrite support.

Features:
- Deterministic synthesis for task_type == "rewrite_project" (no external calls).
- LLM-first helpers used by MockEngineV3:
  - generate_initial_question(...)
  - generate_next_question(...)
  - evaluate_answer(...)
  - improve_answer(...)
  - generate_full_report(...)

Notes:
- call_llm and JSON parsing are resilient; functions return {} or "" on parse failure
  so callers can fall back to deterministic logic.
- Replace/extend `MODEL_NAME` and any model selection logic as needed.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, Optional, Any
from dotenv import load_dotenv

# provider SDKs (optional)
from openai import OpenAI  # used as Groq-compatible client in your code
import google.generativeai as genai

from backend.config import get_settings

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

settings = get_settings()
logger = logging.getLogger(__name__)

# Model selections
MODEL_NAME = os.environ.get("GROQ_MODEL", "llama-3.1-8b-instant")
GEMINI_MODEL = getattr(settings, "GEMINI_MODEL", "gemini-pro")

# Initialize Groq-like OpenAI client if API key present
client: Optional[OpenAI] = None
_groq_api_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
if _groq_api_key:
    try:
        client = OpenAI(base_url="https://api.groq.com/openai/v1", api_key=_groq_api_key)
        logger.info("LLM Engine: Connected to Groq-compatible API.")
    except Exception as e:
        logger.exception("Groq/OpenAI client init failed: %s", e)
        client = None

# Configure genai (Gemini) if key present
_gemini_key = getattr(settings, "GEMINI_API_KEY", None)
if _gemini_key:
    try:
        genai.configure(api_key=_gemini_key)
        logger.info("LLM Engine: Gemini (genai) configured.")
    except Exception:
        logger.exception("genai configure failed; continuing without it.")


class LLMEngine:
    # ------------------------
    # Deterministic helpers (existing behavior preserved)
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
        Deterministic synthesis (used for task_type == 'rewrite_project').
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

        lc = re.sub(r'^\s*(i am|i\'m|i|we|we\'re|we are)\s+', '', lc, flags=re.IGNORECASE).strip()

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
        rest_words = rest.split()
        if len(rest_words) > 12:
            rest = " ".join(rest_words[:12])

        if rest:
            rest = rest[0].upper() + rest[1:] if rest[0].isalpha() else rest
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

        sentence = LLMEngine._enforce_word_limit(sentence, max_words=35)
        if not re.search(r'[\.!?]$', sentence):
            sentence = sentence.rstrip('.') + '.'
        return sentence

    # ------------------------
    # Low-level LLM call (Groq -> Gemini)
    # Returns raw text output (string). Does not parse JSON.
    # ------------------------
    @staticmethod
    def _call_llm(messages: list, max_tokens: int = 512, temperature: float = 0.1) -> str:
        raw_text = ""
        # Try Groq/OpenAI-compatible client first
        if client:
            try:
                resp = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                raw_text = getattr(resp.choices[0].message, "content", "") or ""
                logger.debug("Groq response length=%d", len(raw_text or ""))
            except Exception as e:
                logger.exception("Groq call failed: %s", e)
                raw_text = ""

        # Fallback to Gemini (genai)
        if not raw_text and _gemini_key:
            try:
                # Use a simple concatenated prompt for genai
                full_prompt = "\n".join([m["content"] for m in messages if m.get("role") in ("system", "user")])
                model = genai.GenerativeModel(GEMINI_MODEL)
                resp = model.generate_content(full_prompt)
                raw_text = getattr(resp, "text", "") or str(resp)
                logger.debug("Gemini response length=%d", len(raw_text or ""))
            except Exception as e:
                logger.exception("genai call failed: %s", e)
                raw_text = ""

        # Final safety: remove code fences and tidy whitespace
        if raw_text:
            cleaned = re.sub(r"```(?:json)?\s*", "", raw_text, flags=re.IGNORECASE)
            cleaned = cleaned.replace("`", "").replace("**", "").strip()
            cleaned = re.sub(r"\r\n", "\n", cleaned)
            cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
            return cleaned.strip()

        return ""

    # ------------------------
    # JSON helper: attempt to parse JSON from model text robustly
    # ------------------------
    @staticmethod
    def _safe_parse_json(text: str) -> Optional[Dict[str, Any]]:
        if not text:
            return None
        # Try direct parse
        try:
            return json.loads(text)
        except Exception:
            # Extract the first {...} block
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1 and end > start:
                candidate = text[start:end+1]
                try:
                    return json.loads(candidate)
                except Exception:
                    # attempt to fix common issues: single quotes -> double
                    cand2 = candidate.replace("'", '"')
                    try:
                        return json.loads(cand2)
                    except Exception:
                        return None
            return None

    # ------------------------
    # Public API
    # ------------------------
    @staticmethod
    def generate_response(prompt: str, task_type: str = "chat", role: str = "General") -> str:
        """
        General-purpose text response. If task_type == 'rewrite_project' use deterministic synthesis.
        Otherwise call LLM and return cleaned text.
        """
        if task_type == "rewrite_project":
            return LLMEngine._synthesize_from_input(prompt)

        # Build system/user messages based on task_type
        if task_type == "mock_interview":
            system_msg = f"You are a concise interviewer for role: {role}."
        elif task_type == "improve_experience":
            system_msg = "You are a Career Coach. Rewrite the input into a single powerful bullet point. Use an action verb; quantify when possible."
        elif task_type == "refine_bio":
            system_msg = "You are a Resume Editor. Reformat the bio to be professional and confident. Max 40 words. No markdown."
        else:
            system_msg = f"You are a helpful assistant. Role: {role}."

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"Input: {prompt}\n\nOutput:"}
        ]

        raw = LLMEngine._call_llm(messages, max_tokens=600, temperature=0.15)
        if not raw:
            return "AI Service did not return a response."
        return raw.strip()

    # ------------------------
    # Higher-level helpers (return dicts or empty dict on parse failure)
    # ------------------------
    def generate_initial_question(self, role: str, difficulty: str = "Medium", personality: str = "") -> Dict[str, Any]:
        """
        Ask LLM to provide a single JSON: { "question": "..." }
        """
        system_msg = f"You are an interviewer. {personality} Produce one clear interview question for role '{role}' at difficulty '{difficulty}'. Return JSON: {{ 'question': '...' }}"

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": "Return JSON only."}
        ]

        raw = self._call_llm(messages, max_tokens=160, temperature=0.2)
        parsed = self._safe_parse_json(raw)
        if parsed and "question" in parsed:
            return parsed
        # also accept simple string (plain question)
        if raw:
            return {"question": raw.strip()}
        return {}

    def generate_next_question(self, role: str, difficulty: str, last_answer: Optional[str], personality: str = "") -> Dict[str, Any]:
        """
        Generate follow-up or next question. Return JSON { "question": "..." } or {}.
        """
        system_msg = f"You are an interviewer. {personality} Given role '{role}' and difficulty '{difficulty}', provide the next question. If last_answer exists, adapt the question as a follow-up. Return JSON: {{ 'question': '...' }}."
        user_content = f"last_answer: {json.dumps(last_answer)}" if last_answer else "No last answer provided."
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_content}
        ]
        raw = self._call_llm(messages, max_tokens=200, temperature=0.25)
        parsed = self._safe_parse_json(raw)
        if parsed and "question" in parsed:
            return parsed
        if raw:
            return {"question": raw.strip()}
        return {}

    def evaluate_answer(self, answer: str, question: str, role: str, personality: str = "", resume_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Ask the LLM to evaluate the answer. Expect JSON with keys:
          score (0-100), feedback (str), strengths (list), weaknesses (list)
        Returns parsed dict or {} if model didn't return parseable JSON.
        """
        system_msg = f"You are an interviewer & evaluator. {personality} Evaluate candidate's answer for role '{role}'. Prefer concise factual scoring."
        user_prompt = (
            f"Question: {question}\n"
            f"Answer: {answer}\n\n"
            "Return JSON: {\"score\": 0-100, \"feedback\":\"...\", \"strengths\": [..], \"weaknesses\": [..]}."
        )
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ]
        raw = self._call_llm(messages, max_tokens=300, temperature=0.15)
        parsed = self._safe_parse_json(raw)
        if parsed and "score" in parsed:
            # coerce numeric types
            try:
                parsed["score"] = int(parsed["score"])
            except Exception:
                pass
            return parsed
        # As a helpful fallback, attempt to extract a simple numeric score in text
        if raw:
            # e.g., "Score: 72/100 — feedback..."
            m = re.search(r"score[:\s]+(\d{1,3})", raw, re.IGNORECASE)
            if m:
                try:
                    score = int(m.group(1))
                    return {"score": score, "feedback": raw.strip(), "strengths": [], "weaknesses": []}
                except Exception:
                    pass
        return {}

    def improve_answer(self, answer: str, question: str, role: str, personality: str = "") -> Dict[str, Any]:
        """
        Request an improved/rewrite of the user's answer.
        Returns { "improved_answer": "..." } or {}.
        """
        system_msg = f"You are an interviewer and writing coach. {personality} Rewrite the answer to be concise, impactful, and quantifying where reasonable. Return JSON: {{'improved_answer': '...'}}"
        user_prompt = f"Question: {question}\nInput Answer: {answer}\nReturn JSON only."
        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ]
        raw = self._call_llm(messages, max_tokens=300, temperature=0.2)
        parsed = self._safe_parse_json(raw)
        if parsed and ("improved_answer" in parsed or "rewrite" in parsed or "rewrite_text" in parsed):
            # normalize key
            if "improved_answer" not in parsed:
                for k in ("rewrite", "rewrite_text", "improved"):
                    if k in parsed:
                        parsed = {"improved_answer": parsed[k], **{x: parsed[x] for x in parsed if x not in (k,)}}
                        break
            return parsed
        if raw:
            return {"improved_answer": raw.strip()}
        return {}

    def generate_full_report(self, session: Dict, personality: str = "") -> Dict[str, Any]:
        """
        Ask the model to synthesize a full report for the entire session.
        Expect JSON with keys:
          overall_score, dimensions {communication, technical_depth, structure, confidence},
          strengths, weaknesses, quick_wins (list of {title,description}), transcript (list)
        Returns parsed dict or {}.
        """
        system_msg = f"You are an interviewer and analyst. {personality} Produce a JSON report summarizing the session with overall_score (0-100), dimensions, strengths, weaknesses, quick_wins, transcript."
        # Truncate session for prompt safety
        try:
            short_session = json.dumps(session, default=str)[:4000]
        except Exception:
            short_session = "{}"
        user_prompt = f"Session: {short_session}\nReturn JSON only."

        messages = [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": user_prompt}
        ]
        raw = self._call_llm(messages, max_tokens=1200, temperature=0.15)
        parsed = self._safe_parse_json(raw)
        if parsed and "overall_score" in parsed:
            return parsed
        # fallback: if text contains something useful, return text in 'notes' to let caller fallback
        if raw:
            return {"notes": "LLM returned unparsable report; see raw_text", "raw_text": raw}
        return {}

    # Keep existing resume generator entrypoint from earlier file (optional)
    def generate_resume(self, profile_data: dict, job_description: str, style: str = "modern") -> Dict[str, Any]:
        """
        High-level resume generation. Attempts Groq -> Gemini.
        If unavailable, returns a small mock JSON.
        """
        system_msg = (
            "You are an expert Resume Writer. Output strictly valid JSON. "
            "Do NOT include markdown formatting or code fences."
        )
        prompt = f"""
REQUIRED STYLE: {style.upper()}
USER PROFILE:
{json.dumps(profile_data)}
JOB DESCRIPTION:
{job_description}
OUTPUT SCHEMA (JSON ONLY):
{{ "resume_markdown": "...", "suggestions": ["..."] }}
"""
        messages = [{"role": "system", "content": system_msg}, {"role": "user", "content": prompt}]
        raw = self._call_llm(messages, max_tokens=1600, temperature=0.25)
        parsed = self._safe_parse_json(raw)
        if isinstance(parsed, dict):
            return parsed
        # try to extract {...}
        if raw:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    return json.loads(raw[start:end+1])
                except Exception:
                    pass
        # final mock fallback
        return {
            "resume_markdown": "# Mock Resume\n\nAI Service Unavailable.",
            "suggestions": ["Check API Keys (GROQ_API_KEY, GEMINI_API_KEY)", "Restart backend after setting keys"]
        }
