# backend/services/mock_engine.py
from sqlalchemy.orm import Session
from backend import models
from backend.services.llm_engine import LLMEngine
from datetime import datetime
import json

class MockService:
    
    @staticmethod
    def get_next_question(session_id: int, db: Session):
        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session:
            return None

        # Check if finished
        if session.current_question_index >= session.total_questions:
            session.status = "completed"
            db.commit()
            return {"status": "completed"}

        # Generate Question via AI
        prompt = f"Role: {session.target_role}, Difficulty: {session.difficulty}, Question Number: {session.current_question_index + 1}"
        
        # If resume is attached, we could append resume context here (Phase 3)
        
        question_text = LLMEngine.generate_response(prompt, task_type="generate_question")
        
        # Save to DB
        exchange = models.InterviewExchange(
            session_id=session.id,
            question_order=session.current_question_index + 1,
            question_text=question_text
        )
        db.add(exchange)
        
        # Update Session State
        session.current_question_index += 1
        session.status = "in_progress"
        db.commit()
        db.refresh(exchange)
        
        return {
            "status": "in_progress",
            "question_id": exchange.id,
            "question_text": question_text,
            "current_index": session.current_question_index,
            "total_questions": session.total_questions
        }

    @staticmethod
    def submit_answer(exchange_id: int, user_answer: str, db: Session):
        exchange = db.query(models.InterviewExchange).filter(models.InterviewExchange.id == exchange_id).first()
        if not exchange:
            return None
            
        # 1. Save Answer
        exchange.user_answer = user_answer
        
        # 2. Generate Micro-Feedback (Fast evaluation)
        prompt = f"Question: {exchange.question_text}\nAnswer: {user_answer}"
        feedback = LLMEngine.generate_response(prompt, task_type="evaluate_answer")
        exchange.ai_feedback = feedback
        
        # 3. Commit
        db.commit()
        
        return {
            "feedback": feedback
        }

    @staticmethod
    def end_session_and_score(session_id: int, db: Session):
        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session:
            return None

        # 1. Compile Transcript & Generate Improvements
        transcript_text = ""
        for ex in session.exchanges:
            transcript_text += f"Q: {ex.question_text}\nA: {ex.user_answer}\n\n"
            
            # --- NEW: Generate Improved Answer for every question ---
            # (In production, consider limiting to low-scoring answers to save tokens)
            try:
                improve_prompt = f"Question: {ex.question_text}\nUser Answer: {ex.user_answer}"
                better_version = LLMEngine.generate_response(improve_prompt, task_type="improve_mock_answer")
                ex.improved_answer = better_version
            except Exception as e:
                # If improvement fails, keep improved_answer empty and continue
                ex.improved_answer = None
                print(f"Improve-answer error for exchange {ex.id}: {e}")
            # --------------------------------------------------------

        if not transcript_text:
            transcript_text = "No answers recorded."

        # 2. Call AI for Analysis (Existing logic)
        prompt = f"Role: {session.target_role}\n\nTranscript:\n{transcript_text}"
        
        try:
            raw_json = LLMEngine.generate_response(prompt, task_type="generate_interview_report")
            # Clean JSON (remove markdown wrappers if any)
            clean_json = raw_json.replace("```json", "").replace("```", "").strip()
            data = json.loads(clean_json)
            
            # 3. Save Scores to DB
            scores = data.get("scores", {})
            session.overall_score = scores.get("overall", 50)
            session.technical_score = scores.get("technical", 50)
            session.communication_score = scores.get("communication", 50)
            session.structure_score = scores.get("structure", 50)
            session.impact_score = scores.get("impact", 50)
            session.behavioral_score = scores.get("behavioral", 50)
            
            # 4. Save Text Report
            session.feedback_report = json.dumps(data.get("feedback", {}))
            session.status = "completed"
            
            # Commit all changes (scores + improved answers saved above)
            db.commit()
            
            return {
                "status": "success",
                "scores": scores,
                "feedback": data.get("feedback", {})
            }
            
        except Exception as e:
            print(f"Scoring Error: {e}")
            # Fallback for error
            return {
                "status": "error", 
                "message": "AI scoring failed."
            }
            
    @staticmethod
    def get_results(session_id: int, db: Session):
        session = db.query(models.InterviewSession).filter(models.InterviewSession.id == session_id).first()
        if not session or session.status != "completed":
            return None
            
        feedback = json.loads(session.feedback_report) if session.feedback_report else {}
        
        # --- NEW: Serialize Transcript ---
        transcript = []
        for ex in session.exchanges:
            transcript.append({
                "question": ex.question_text,
                "user_answer": ex.user_answer,
                "feedback": ex.ai_feedback,
                "improved_answer": ex.improved_answer
            })
        
        return {
            "overall_score": session.overall_score,
            "dimensions": {
                "Technical": session.technical_score,
                "Communication": session.communication_score,
                "Structure": session.structure_score,
                "Impact": session.impact_score,
                "Behavioral": session.behavioral_score
            },
            "feedback": feedback,
            "transcript": transcript  # <--- Send to frontend
        }
