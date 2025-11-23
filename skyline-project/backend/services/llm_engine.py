import logging
import json
import os
from pathlib import Path
from typing import Dict
from dotenv import load_dotenv
from openai import OpenAI
from backend.config import get_settings

# --- 1. FORCE LOAD .ENV FILE ---
# This is the critical fix. It calculates the exact path to your .env file
# relative to this script, ensuring it loads even if you run the server from the root.
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

settings = get_settings()
logger = logging.getLogger(__name__)

# --- 2. CONFIGURATION ---
# This uses the currently supported Groq model
MODEL_NAME = "llama-3.1-8b-instant"

# --- 3. INITIALIZE CLIENT ---
_groq_api_key = os.environ.get("GROQ_API_KEY") or getattr(settings, "GROQ_API_KEY", None)
client = None

if _groq_api_key:
    try:
        client = OpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=_groq_api_key
        )
        # Print a clear success message to the terminal
        print(f"✅ LLM Engine: Connected to Groq using model: {MODEL_NAME}")
    except Exception as e:
        print(f"❌ LLM Engine: Failed to initialize client: {e}")
        client = None
else:
    print("⚠️ LLM Engine: No GROQ_API_KEY found. Running in MOCK MODE.")


class LLMEngine:
    
    @staticmethod
    def generate_resume(profile_data: dict, job_description: str, style: str = "modern") -> Dict:
        """
        Generates a resume based on profile, JD, and selected style.
        Returns a dict with 'resume_markdown' and 'suggestions'.
        """
        # Check if client is active
        if not client:
            return LLMEngine._get_mock_resume()

        # System Prompt: Enforce JSON output
        system_msg = (
            "You are an expert Resume Writer. "
            "Output strictly valid JSON. "
            "Do not output markdown formatting (like ```json) around the response."
        )

        # User Prompt: Inject Style, Profile, and JD
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

            content = response.choices[0].message.content
            
            # Clean formatting (remove code blocks if AI adds them)
            clean_text = content.strip().replace("```json", "").replace("```", "").strip()
            
            # Attempt to parse JSON
            try:
                return json.loads(clean_text)
            except json.JSONDecodeError:
                # Fallback: Try to find the JSON object inside text
                start = clean_text.find("{")
                end = clean_text.rfind("}")
                if start != -1 and end != -1:
                    return json.loads(clean_text[start:end+1])
                raise

        except Exception as e:
            logger.error(f"LLM Generation Error: {e}")
            return LLMEngine._get_mock_resume()

    @staticmethod
    def generate_response(prompt: str, task_type: str = "chat", role: str = "General") -> str:
        """
        Handles general Chat and Mock Interview logic.
        """
        if not client:
            if task_type == "mock_interview":
                return f"[DEMO] That's a good answer! (Mock Mode - API Key missing)"
            return "I am currently in Demo Mode. Please configure your API key."

        try:
            system_msg = "You are a helpful career coach."
            
            if task_type == "mock_interview":
                system_msg = f"""
                You are an expert interviewer for the role: {role}.
                1. Briefly evaluate the user's answer.
                2. Ask the NEXT relevant question.
                3. Keep it conversational and short.
                """

            response = client.chat.completions.create(
                model=MODEL_NAME,
                messages=[
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7,
                max_tokens=800,
            )
            return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM Chat Error: {e}")
            return "Sorry, I encountered an error connecting to the AI."

    @staticmethod
    def _get_mock_resume() -> Dict:
        """
        Fallback data when API is unavailable.
        """
        return {
            "resume_markdown": "# Mock Resume\n\n**API Key missing or invalid.**\n\nPlease check your backend logs to see why the key wasn't loaded.",
            "suggestions": ["Check .env file location", "Restart Uvicorn Server"]
        }