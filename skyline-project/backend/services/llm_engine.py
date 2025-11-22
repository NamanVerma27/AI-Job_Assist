import logging
import json
import google.generativeai as genai
from backend.config import get_settings

settings = get_settings()
logger = logging.getLogger(__name__)

if settings.GEMINI_API_KEY:
    genai.configure(api_key=settings.GEMINI_API_KEY)

class LLMEngine:
    
    @staticmethod
    def generate_resume(profile_data: dict, job_description: str, style: str = "modern") -> dict:
        """
        Generates a resume and insights based on profile and JD.
        Style arg determines the tone/structure.
        """
        # 1. Check for API Key (Mock Mode)
        if not settings.GEMINI_API_KEY:
            return LLMEngine._get_mock_resume()

        # 2. Construct Prompt with Style Injection
        prompt = f"""
        Act as an expert Resume Writer and Career Coach.
        
        REQUIRED STYLE: {style.upper()}
        - If 'MODERN': Use concise, punchy sentences. Focus on metrics and results. Active voice.
        - If 'PROFESSIONAL': Use formal language, traditional structure. Robust descriptions.
        - If 'CREATIVE': Use engaging vocabulary, highlight personality and innovation.
        - If 'ACADEMIC': Focus on education, research, detailed qualifications.

        Task 1: Generate a professional resume in Markdown format tailored to the Job Description below.
        Task 2: Provide 3 short, actionable tips to improve chances for this specific job.

        USER PROFILE:
        {profile_data}

        TARGET JOB DESCRIPTION:
        {job_description}

        Output Format (JSON):
        {{
            "resume_markdown": "# Name...",
            "suggestions": ["Tip 1", "Tip 2", "Tip 3"]
        }}
        """

        try:
            model = genai.GenerativeModel('gemini-pro')
            response = model.generate_content(prompt)
            # Simple cleanup to ensure we get JSON (Gemini sometimes adds backticks)
            clean_text = response.text.replace("```json", "").replace("```", "")
            return json.loads(clean_text)
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return LLMEngine._get_mock_resume()

    @staticmethod
    def generate_response(prompt: str, task_type: str = "chat", role: str = "General") -> str:
        """
        Handles Chat and Mock Interview logic.
        """
        # 1. Mock Mode Fallback
        if not settings.GEMINI_API_KEY:
            if task_type == "mock_interview":
                return f"[DEMO MODE] That is a good answer! For a {role} role, you should also mention X. \n\nNext Question: Describe a challenging project you worked on."
            return "I am currently running in **Demo Mode**. I can help you simulate an interview or discuss career strategies!"

        # 2. Live Gemini Mode
        try:
            model = genai.GenerativeModel('gemini-pro')
            
            # Construct a specialized prompt based on task
            if task_type == "mock_interview":
                system_instruction = f"""
                You are an expert technical interviewer for the role of: {role}.
                The user just gave an answer (or started the session).
                
                Your Goal:
                1. Briefly evaluate the user's last answer (if any).
                2. Ask the NEXT relevant interview question (technical or behavioral).
                3. Keep it professional but encouraging.
                4. Do not write long essays; keep it conversational.
                """
                full_prompt = f"{system_instruction}\n\nUser Input: {prompt}"
            else:
                full_prompt = f"Act as a Career Coach. User: {prompt}"

            response = model.generate_content(full_prompt)
            return response.text
        except Exception as e:
            logger.error(f"LLM Error: {e}")
            return "Error connecting to AI service."

    @staticmethod
    def _get_mock_resume() -> dict:
        """
        Fallback data for when keys are missing or API fails.
        """
        return {
            "resume_markdown": """
# JOHN DOE
**Software Engineer**
*City, State | email@example.com | (555) 123-4567*

## PROFESSIONAL SUMMARY
Results-oriented software developer with experience in Python and React. Passionate about building scalable web applications.

## EXPERIENCE
**Software Developer | Tech Solutions Inc.**
*Jan 2022 - Present*
- Developed REST APIs using FastAPI.
- Improved frontend performance by 20% using React best practices.

## SKILLS
- **Languages:** Python, JavaScript, SQL
- **Frameworks:** React, FastAPI, Django
            """,
            "suggestions": [
                "Your profile lacks specific 'Cloud' experience mentioned in the JD.",
                "Highlight your 'Team Leadership' skills more.",
                "Add metrics to your project descriptions (e.g., 'Reduced latency by 15%')."
            ]
        }