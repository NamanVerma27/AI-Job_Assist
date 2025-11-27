# backend/services/mock_engine.py
import logging
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_engine import LLMEngine
from datetime import datetime
import json

logger = logging.getLogger("mock_service")


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

        # End if already completed
        if session.current_question_index >= session.total_questions:
            session.status = "completed"
            db.commit()
            return {"status": "completed"}

        # Generate AI question
        prompt = (
            f"Role: {session.target_role}, "
            f"Difficulty: {session.difficulty}, "
            f"Question Number: {session.current_question_index + 1}"
        )

        question_text = LLMEngine.generate_response(
            prompt, task_type="generate_question"
        )

        # Save exchange
        exchange = models.InterviewExchange(
            session_id=session.id,
            question_order=session.current_question_index + 1,
            question_text=question_text,
        )
        db.add(exchange)

        # Update session
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

        # Save answer
        exchange.user_answer = user_answer.strip() if user_answer else ""

        # Micro-feedback
        prompt = (
            f"Question: {exchange.question_text}\n"
            f"Answer: {exchange.user_answer}"
        )
        feedback = LLMEngine.generate_response(
            prompt, task_type="evaluate_answer"
        )
        exchange.ai_feedback = feedback

        # ---------------------------------------------------------
        # ATOMIC SCORING (deterministic fallback)
        # ---------------------------------------------------------
        ans = exchange.user_answer.lower()

        def word_count(s):
            return len(s.split())

        # Simple heuristic scoring
        exchange.score_correctness = 70 if len(ans) > 20 else 40
        exchange.score_clarity = 60 if "." in ans else 35
        exchange.score_confidence = 65 if "i" not in ans[:5] else 45

        db.commit()

        return {"feedback": feedback}

    # ---------------------------------------------------------
    # End session + Full scoring
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
        transcript_text = ""

        # Pick improved-answer candidates (short answers only)
        improve_candidates = []
        for ex in exchanges:
            ua = (ex.user_answer or "").strip()
            if not ua or len(ua.split()) < 15:
                improve_candidates.append(ex)

        improve_candidates = improve_candidates[:3]

        # Build transcript
        for ex in exchanges:
            ua = ex.user_answer if ex.user_answer else "[no answer provided]"
            transcript_text += f"Q: {ex.question_text}\nA: {ua}\n\n"

        # Generate improved answers
        for ex in improve_candidates:
            try:
                prompt = (
                    f"Question: {ex.question_text}\n"
                    f"User Answer: {ex.user_answer}"
                )
                improved = LLMEngine.generate_response(
                    prompt, task_type="improve_mock_answer"
                )
                ex.improved_answer = improved
            except Exception as e:
                logger.error(f"Improve-answer error for ex {ex.id}: {e}")
                ex.improved_answer = None

        db.commit()

        if not transcript_text:
            transcript_text = "No answers recorded."

        # ------------------------------
        # CALL AI FOR FULL REPORT
        # ------------------------------
        prompt = (
            f"Role: {session.target_role}\n\n"
            f"Transcript:\n{transcript_text}"
        )

        raw_json = LLMEngine.generate_response(
            prompt, task_type="generate_interview_report"
        )

        if not raw_json:
            logger.error("AI report empty or failed.")
            return {"status": "error", "message": "AI scoring failed"}

        # Parse JSON safely
        try:
            start = raw_json.find("{")
            end = raw_json.rfind("}")
            json_block = raw_json[start : end + 1]
            data = json.loads(json_block)
        except Exception as e:
            logger.error(f"Report JSON decode error: {e}")
            return {"status": "error", "message": "Parsing failed"}

        # Save scores
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

        return {
            "status": "success",
            "scores": scores,
            "feedback": data.get("feedback", {}),
        }

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

        feedback = (
            json.loads(session.feedback_report)
            if session.feedback_report
            else {}
        )

        transcript = []
        for ex in session.exchanges or []:
            transcript.append(
                {
                    "question": ex.question_text,
                    "user_answer": ex.user_answer
                    if ex.user_answer
                    else "[no answer provided]",
                    "feedback": ex.ai_feedback,
                    "improved_answer": ex.improved_answer,
                }
            )

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
