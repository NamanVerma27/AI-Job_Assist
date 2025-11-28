# backend/services/mock_engine.py
import logging
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_engine import LLMEngine
from datetime import datetime
import json

logger = logging.getLogger("mock_service")

SAFE_Q = "I'm unable to generate the next question right now."
SAFE_FEEDBACK = "Unable to analyze your answer."
SAFE_IMPROVED = "No improved answer available."


class MockService:

    # ---------------------------------------------------------
    # Get the next question
    # ---------------------------------------------------------
    @staticmethod
    def get_next_question(session_id: int, db: Session):
        session = (
            db.query(models.InterviewSession)
            .filter(models.InterviewSession.id == session_id)
            .first()
        )
        if not session:
            return None

        if session.current_question_index >= session.total_questions:
            session.status = "completed"
            db.commit()
            return {"status": "completed"}

        prompt = (
            f"Role: {session.target_role}, "
            f"Difficulty: {session.difficulty}, "
            f"Question Number: {session.current_question_index + 1}"
        )

        raw = LLMEngine.generate_response(prompt, task_type="generate_question")
        question_text = raw.strip() if raw else SAFE_Q

        exchange = models.InterviewExchange(
            session_id=session.id,
            question_order=session.current_question_index + 1,
            question_text=question_text,
        )
        db.add(exchange)

        session.current_question_index += 1
        session.status = "in_progress"
        db.commit()
        db.refresh(exchange)

        return {
            "status": "in_progress",
            "question_id": exchange.id,
            "question_text": question_text,
            "current_index": session.current_question_index,
            "total_questions": session.total_questions,
        }

    # ---------------------------------------------------------
    # Submit answer
    # ---------------------------------------------------------
    @staticmethod
    def submit_answer(exchange_id: int, user_answer: str, db: Session):
        exchange = (
            db.query(models.InterviewExchange)
            .filter(models.InterviewExchange.id == exchange_id)
            .first()
        )
        if not exchange:
            return None

        ua = (user_answer or "").strip()
        exchange.user_answer = ua

        prompt = f"Question: {exchange.question_text}\nAnswer: {ua}"

        raw = LLMEngine.generate_response(prompt, task_type="evaluate_answer")
        feedback = raw.strip() if raw else SAFE_FEEDBACK
        exchange.ai_feedback = feedback

        # Simple heuristic
        ans = ua.lower()
        exchange.score_correctness = 70 if len(ans) > 20 else 40
        exchange.score_clarity = 60 if "." in ans else 35
        exchange.score_confidence = 65 if not ans.startswith("i ") else 45

        db.commit()

        return {"feedback": feedback}

    # ---------------------------------------------------------
    # End session + score
    # ---------------------------------------------------------
    @staticmethod
    def end_session_and_score(session_id: int, db: Session):
        session = (
            db.query(models.InterviewSession)
            .filter(models.InterviewSession.id == session_id)
            .first()
        )
        if not session:
            return None

        exchanges = session.exchanges or []
        transcript = ""

        improve_candidates = []
        for ex in exchanges:
            ua = (ex.user_answer or "").strip()
            if not ua or len(ua.split()) < 15:
                improve_candidates.append(ex)

        improve_candidates = improve_candidates[:3]

        # Build transcript
        for ex in exchanges:
            ua = ex.user_answer or "[no answer provided]"
            transcript += f"Q: {ex.question_text}\nA: {ua}\n\n"

        # Improve answers
        for ex in improve_candidates:
            try:
                prompt = f"Question: {ex.question_text}\nUser Answer: {ex.user_answer}"
                raw = LLMEngine.generate_response(prompt, task_type="improve_mock_answer")
                ex.improved_answer = raw.strip() if raw else SAFE_IMPROVED
            except Exception:
                ex.improved_answer = SAFE_IMPROVED

        db.commit()

        if not transcript.strip():
            transcript = "No answers recorded."

        # Final report
        prompt = f"Role: {session.target_role}\n\nTranscript:\n{transcript}"

        raw_json = LLMEngine.generate_response(
            prompt, task_type="generate_interview_report"
        )

        if not raw_json:
            return {"status": "error", "message": "AI scoring failed"}

        # Attempt to parse JSON
        try:
            start = raw_json.find("{")
            end = raw_json.rfind("}")
            if start == -1 or end == -1:
                raise ValueError("Invalid JSON boundary")
            data = json.loads(raw_json[start : end + 1])
        except Exception as e:
            logger.error(f"JSON decode error: {e}")
            return {"status": "error", "message": "Parsing failed"}

        scores = data.get("scores", {})

        session.overall_score = scores.get("overall", 50)
        session.technical_score = scores.get("technical", 50)
        session.communication_score = scores.get("communication", 50)
        session.structure_score = scores.get("structure", 50)
        session.impact_score = scores.get("impact", 50)
        session.behavioral_score = scores.get("behavioral", 50)

        session.feedback_report = json.dumps(data.get("feedback", {}))
        session.status = "completed"

        db.commit()

        return {"status": "success", "scores": scores, "feedback": data.get("feedback", {})}

    # ---------------------------------------------------------
    # Get final results
    # ---------------------------------------------------------
    @staticmethod
    def get_results(session_id: int, db: Session):
        session = (
            db.query(models.InterviewSession)
            .filter(models.InterviewSession.id == session_id)
            .first()
        )
        if not session or session.status != "completed":
            return None

        feedback = {}
        if session.feedback_report:
            try:
                feedback = json.loads(session.feedback_report)
            except:
                feedback = {}

        transcript = []
        for ex in session.exchanges or []:
            transcript.append({
                "question": ex.question_text,
                "user_answer": ex.user_answer or "[no answer provided]",
                "feedback": ex.ai_feedback,
                "improved_answer": ex.improved_answer,
            })

        return {
            "overall_score": session.overall_score,
            "dimensions": {
                "technical": session.technical_score,
                "communication": session.communication_score,
                "structure": session.structure_score,
                "impact": session.impact_score,
                "behavioral": session.behavioral_score,
            },
            "feedback": feedback,
            "transcript": transcript,
        }
