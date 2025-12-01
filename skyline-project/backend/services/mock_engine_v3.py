# backend/services/mock_engine_v3.py
"""
Hybrid Mock Engine (LLM-first, deterministic fallback)
- Light in-memory session store for quick testing
- Calls llm_engine for LLM behavior; falls back to deterministic functions
"""
import uuid
import time
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from backend.services.llm_engine import LLMEngine
from backend.services.question_bank import QuestionBank
from backend.services.eval_rules import evaluate_answer_rule_based
from backend.services.report_builder import build_report_rule_based

# Simple in-memory session store
_SESSIONS: Dict[str, Any] = {}

# Supported personalities (in prompts + behavior)
PERSONALITIES = {
    "neutral": "You are a neutral technical interviewer.",
    "strict": "You are a strict senior engineer interviewer: be concise and demanding.",
    "friendly": "You are a friendly mentor interviewer: encouraging and constructive.",
    "hiring_manager": "You are a hiring manager: focus on impact, leadership, and business outcomes.",
    "behavioral": "You are behavioral-focused: ask STAR style follow-ups and probe for context and results."
}

@dataclass
class Exchange:
    question_id: str
    question_text: str
    user_answer: Optional[str] = None
    evaluation: Optional[Dict] = None
    improved_answer: Optional[str] = None
    timestamp: float = field(default_factory=time.time)

class MockEngineV3:
    def __init__(self):
        self.llm = LLMEngine()
        self.bank = QuestionBank()

    def start_session(self, role: str, difficulty: str = "Medium", question_count: int = 5, resume_id: Optional[str] = None, personality: str = "neutral"):
        sid = str(uuid.uuid4())
        personality = personality if personality in PERSONALITIES else "neutral"
        sess = {
            "id": sid,
            "role": role,
            "difficulty": difficulty,
            "question_count": int(question_count),
            "resume_id": resume_id,
            "personality": personality,
            "created_at": time.time(),
            "completed": False,
            "history": [],  # list of Exchange dicts
            "current_index": 0
        }
        _SESSIONS[sid] = sess

        # Generate initial question via LLM (fallback to bank)
        try:
            q = self.llm.generate_initial_question(role=role, difficulty=difficulty, personality=PERSONALITIES[personality])
            if not q or "question" not in q:
                raise Exception("LLM returned unexpected")
            first_q = q["question"]
        except Exception:
            first_q = self.bank.get_question(role=role, difficulty=difficulty)

        exchange = Exchange(question_id=str(uuid.uuid4()), question_text=first_q)
        sess["history"].append(exchange.__dict__)
        sess["current_index"] = 1
        return {"session_id": sid, "question": first_q, "role": role}

    def _get_session(self, session_id: str):
        return _SESSIONS.get(session_id)

    def next_question(self, session_id: str):
        sess = self._get_session(session_id)
        if not sess:
            return None
        if sess["completed"] or sess["current_index"] >= sess["question_count"]:
            # mark completed if finished
            sess["completed"] = True
            return {"status": "completed", "message": "All questions answered"}
        # LLM-informed next question (uses last answer if present)
        last_exchange = sess["history"][-1] if sess["history"] else None
        role = sess["role"]
        difficulty = sess["difficulty"]
        personality = PERSONALITIES.get(sess["personality"], PERSONALITIES["neutral"])
        try:
            snippet = last_exchange.get("user_answer") if last_exchange else None
            qobj = self.llm.generate_next_question(role=role, difficulty=difficulty, last_answer=snippet, personality=personality)
            qtext = qobj.get("question") if qobj and "question" in qobj else None
            if not qtext:
                raise Exception("LLM didn't provide question")
        except Exception:
            qtext = self.bank.get_question(role=role, difficulty=difficulty)

        new_ex = Exchange(question_id=str(uuid.uuid4()), question_text=qtext)
        sess["history"].append(new_ex.__dict__)
        sess["current_index"] += 1
        return {"question_id": new_ex.question_id, "question": qtext, "current_index": sess["current_index"], "total_questions": sess["question_count"]}

    def submit_answer(self, session_id: str, answer: str):
        sess = self._get_session(session_id)
        if not sess:
            return None
        # Attach to last exchange
        last = sess["history"][-1]
        last["user_answer"] = answer

        # Try LLM evaluation
        personality = PERSONALITIES.get(sess["personality"], PERSONALITIES["neutral"])
        try:
            eval_res = self.llm.evaluate_answer(answer=answer, question=last["question_text"], role=sess["role"], personality=personality, resume_id=sess.get("resume_id"))
            # Expect evaluation dict with score/feedback/improved_answer
            if not isinstance(eval_res, dict) or "score" not in eval_res:
                raise Exception("LLM returned unexpected shape")
        except Exception:
            # fallback deterministic evaluation
            eval_res = evaluate_answer_rule_based(question=last["question_text"], answer=answer)

        last["evaluation"] = eval_res
        # optionally get improved answer from LLM (best-effort)
        improved = None
        try:
            improved = self.llm.improve_answer(answer=answer, question=last["question_text"], role=sess["role"], personality=personality)
            if isinstance(improved, dict):
                improved = improved.get("improved_answer") or improved.get("rewrite") or None
        except Exception:
            improved = None

        last["improved_answer"] = improved
        return {
            "evaluation": eval_res,
            "next_question": None if sess["current_index"] >= sess["question_count"] else {"current_index": sess["current_index"], "total": sess["question_count"]},
            "session_id": session_id,
            "history_count": len(sess["history"])
        }

    def end_session(self, session_id: str):
        sess = self._get_session(session_id)
        if not sess:
            return None
        # Try LLM report
        personality = PERSONALITIES.get(sess["personality"], PERSONALITIES["neutral"])
        try:
            report = self.llm.generate_full_report(session=sess, personality=personality)
            if not isinstance(report, dict) or "overall_score" not in report:
                raise Exception("LLM returned unexpected report")
        except Exception:
            report = build_report_rule_based(session=sess)

        sess["completed"] = True
        sess["report"] = report
        return {"session_id": session_id, "report": report}

    def get_report(self, session_id: str):
        sess = self._get_session(session_id)
        if not sess:
            return None
        return sess.get("report")
