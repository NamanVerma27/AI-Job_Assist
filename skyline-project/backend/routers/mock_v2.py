# backend/routers/mock_v2.py
"""
Lightweight Mock Interview router (drop-in replacement).
Provides:
 - /mock/start            (legacy simple start)
 - /mock/question         (legacy fetch question)
 - /mock/answer           (legacy submit answer)
 - /mock/end              (legacy finish)
 - /mock-v2/start-session
 - /mock-v2/{session_id}/next
 - /mock-v2/submit-answer
 - /mock-v2/{session_id}/end
 - /mock-v2/{session_id}/results

This file embeds:
 - a tiny question bank
 - an in-router deterministic evaluator (safe, fast, no external deps)
 - an in-memory session store (for dev). Persist externally in production.
"""

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import random
import time
import re

router = APIRouter(prefix="/mock-v2", tags=["Mock Interview V2"])

# --- Simple in-memory session store (dev only) ---
SESSIONS: Dict[str, Dict[str, Any]] = {}

# --- Basic question bank (expand as needed) ---
QUESTION_BANK = {
    "frontend": [
        "Explain the difference between CSS Grid and Flexbox and when you'd use each.",
        "How does the browser render a web page from HTML/CSS/JS?",
        "What is event delegation and why is it useful?",
        "Describe React component lifecycle and hooks replacement for lifecycle methods.",
        "How would you improve performance of a slow React application?"
    ],
    "backend": [
        "Explain ACID vs BASE properties of databases.",
        "What is a memory leak in a server app and how would you troubleshoot it?",
        "Describe how HTTP/2 improves over HTTP/1.1.",
        "How would you design an API rate limiter?",
        "Explain transactions and isolation levels in relational DBs."
    ],
    "general": [
        "Tell me about a time you faced a technical challenge and how you solved it.",
        "How do you prioritize tasks when given multiple deadlines?",
        "Explain the STAR method for behavioral answers.",
        "Describe a project you led and the outcome.",
        "How do you keep up-to-date with technical trends?"
    ]
}

# small pool of action verbs for evaluation heuristics
ACTION_VERBS = {"led","developed","implemented","created","designed","improved","optimized","built","reduced","increased","launched","resolved","managed","coached","mentored"}

HEDGING_WORDS = {"maybe","might","possibly","sometimes","could","probably","try","attempt","ish","sort of","kind of","might've","maybe"}


# ---------- Request models ----------
class StartReq(BaseModel):
    role: Optional[str] = "general"
    difficulty: Optional[str] = "Medium"
    question_count: Optional[int] = 5
    resume_id: Optional[Any] = None


class SessionReq(BaseModel):
    session_id: str


class AnswerReq(BaseModel):
    session_id: str
    answer: str
    exchange_id: Optional[str] = None


# ---------- Utilities ----------
def _new_session(role: str = "general", question_count: int = 5, difficulty: str = "Medium", resume_id: Optional[Any] = None) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    role_key = role.lower() if role and role.lower() in QUESTION_BANK else "general"
    # pick a shuffled list of questions for session
    qlist = QUESTION_BANK.get(role_key, QUESTION_BANK["general"]).copy()
    random.shuffle(qlist)
    # ensure enough questions (repeat if necessary)
    while len(qlist) < question_count:
        qlist.extend(random.sample(QUESTION_BANK.get(role_key, QUESTION_BANK["general"]), k=len(QUESTION_BANK.get(role_key, QUESTION_BANK["general"]))))
    qlist = qlist[:question_count]

    questions = []
    for i, q in enumerate(qlist, start=1):
        questions.append({
            "question_id": str(uuid.uuid4()),
            "question_text": q,
            "current_index": i,
            "total_questions": question_count
        })

    sess = {
        "session_id": sid,
        "role": role_key,
        "difficulty": difficulty,
        "questions": questions,
        "pointer": 0,  # next question index
        "history": [],  # list of {question_id, question, answer, eval}
        "started_at": time.time(),
        "finished": False,
        "resume_id": resume_id,
        "report": None
    }
    SESSIONS[sid] = sess
    return sess


def _get_session(sid: str) -> Dict[str, Any]:
    s = SESSIONS.get(sid)
    if not s:
        raise HTTPException(status_code=404, detail="session not found")
    return s


# Deterministic / heuristic evaluator (safe fallback)
def deterministic_evaluate_answer(question_text: str, answer_text: str) -> Dict[str, Any]:
    """
    Lightweight scoring heuristics:
    - word_count -> boosts length up to sweet spot
    - action_verbs -> counts presence of action verbs
    - numeric_mentions -> counts numbers (evidence/metrics)
    - leadership_mentions -> simple leadership token hits
    - hedging_count -> penalize hedging words
    Returns a dict with score 0-100, strengths, weaknesses, metrics.
    """
    text = (answer_text or "").strip()
    words = re.findall(r"\w+|[0-9]+", text)
    word_count = len(words)
    # action verbs count (case-insensitive)
    actions = sum(1 for w in words if w.lower() in ACTION_VERBS)
    # numbers (simple digits)
    numeric_mentions = len(re.findall(r"\d+", answer_text))
    # leadership mentions
    leadership = sum(1 for w in words if w.lower() in {"lead","led","manage","managed","mentor","mentored","coached"})
    # hedging
    hedges = sum(1 for w in re.findall(r"\w+\'?\w*|\S", answer_text.lower()) if any(h in w for h in HEDGING_WORDS))

    # length score: prefer moderate answers ~20-120 words
    if word_count == 0:
        length_score = 0
    elif word_count < 10:
        length_score = 15
    elif word_count <= 30:
        length_score = 40
    elif word_count <= 120:
        length_score = 70
    else:
        length_score = 55

    # action score
    action_score = min(20, actions * 8)  # up to 20

    # quantified score
    quantified_score = min(20, numeric_mentions * 8)

    # leadership score
    leadership_score = min(15, leadership * 8)

    # hedging penalty
    hedging_penalty = min(20, hedges * 6)

    raw = {
        "length_score": length_score,
        "action_score": action_score,
        "quantified_score": quantified_score,
        "leadership_score": leadership_score,
        "hedging_penalty": hedging_penalty
    }

    # simple weighted final score
    # weights chosen to prefer clarity + actions + some quant
    score = (
        0.35 * length_score +
        0.30 * action_score +
        0.20 * quantified_score +
        0.15 * leadership_score
    ) - hedging_penalty

    score = max(0, min(100, int(round(score))))

    # strengths / weaknesses text
    strengths = []
    weaknesses = []
    if actions:
        strengths.append(f"Uses action verbs ({actions}).")
    if leadership:
        strengths.append("Shows leadership/ownership.")
    if numeric_mentions:
        strengths.append(f"Provides quantified evidence ({numeric_mentions}).")
    if word_count >= 10 and word_count <= 120:
        strengths.append("Answer length is appropriate.")

    if word_count == 0:
        weaknesses.append("No answer provided.")
    elif word_count < 10:
        weaknesses.append("Answer is short; add more detail and examples.")
    if hedging_penalty:
        weaknesses.append("Hedging language detected; be more assertive.")
    if numeric_mentions == 0:
        weaknesses.append("No quantified evidence provided; add numbers where possible.")

    feedback = f"Score: {score}/100 — length:{word_count}, action:{action_score}, leadership:{leadership_score}, quantified:{quantified_score}, hedging_penalty:{hedging_penalty}. Strengths: {'; '.join(strengths) if strengths else 'None.'} Weaknesses: {'; '.join(weaknesses) if weaknesses else 'None.'}"

    metrics = {
        "word_count": word_count,
        "action_verbs": actions,
        "leadership_mentions": leadership,
        "numeric_mentions": numeric_mentions,
        "hedging_count": hedges,
        "raw_components": raw
    }

    return {
        "score": score,
        "strengths": strengths,
        "weaknesses": weaknesses,
        "feedback": feedback,
        "metrics": metrics
    }


# ---------- Legacy-style endpoints (minimal) ----------
legacy_router = APIRouter(prefix="/mock", tags=["Mock Interview - legacy"])

@legacy_router.post("/start")
def legacy_start(payload: StartReq):
    sess = _new_session(role=payload.role or "general", question_count=payload.question_count or 5, difficulty=payload.difficulty or "Medium", resume_id=payload.resume_id)
    first_q = sess["questions"][0]
    return {"status": "success", "data": {"session_id": sess["session_id"], "question": first_q["question_text"], "role": sess["role"]}}

@legacy_router.post("/question")
def legacy_question(req: SessionReq):
    sess = _get_session(req.session_id)
    ptr = sess["pointer"]
    if ptr >= len(sess["questions"]):
        raise HTTPException(status_code=404, detail="no more questions")
    q = sess["questions"][ptr]
    # do not advance pointer on question fetch; advance on answer
    return {"status": "success", "data": {"question_id": q["question_id"], "question": q["question_text"], "current_index": q["current_index"], "total_questions": q["total_questions"]}}

@legacy_router.post("/answer")
def legacy_answer(req: AnswerReq):
    sess = _get_session(req.session_id)
    ptr = sess["pointer"]
    if ptr >= len(sess["questions"]):
        raise HTTPException(status_code=404, detail="session completed")
    q = sess["questions"][ptr]
    eval_res = deterministic_evaluate_answer(q["question_text"], req.answer)
    # store
    sess["history"].append({
        "question_id": q["question_id"],
        "question": q["question_text"],
        "answer": req.answer,
        "evaluation": eval_res,
        "timestamp": time.time()
    })
    sess["pointer"] += 1
    # prepare next question if any
    next_q = None
    if sess["pointer"] < len(sess["questions"]):
        nq = sess["questions"][sess["pointer"]]
        next_q = {"question_id": nq["question_id"], "question": nq["question_text"], "current_index": nq["current_index"], "total_questions": nq["total_questions"]}
    else:
        next_q = None
    return {"status": "success", "data": {"evaluation": eval_res, "next_question": next_q, "session_id": sess["session_id"], "history_count": len(sess["history"]) } }

@legacy_router.post("/end")
def legacy_end(req: SessionReq):
    sess = _get_session(req.session_id)
    sess["finished"] = True
    # compute report quick summary
    scores = [h["evaluation"]["score"] for h in sess["history"] if h.get("evaluation")]
    overall = int(round(sum(scores)/len(scores))) if scores else 0
    sess["report"] = {
        "overall_score": overall,
        "questions": len(sess["questions"]),
        "answered": len(sess["history"])
    }
    return {"status": "success", "data": {"session_id": sess["session_id"], "report": sess["report"]} }

# mount legacy router to main router will be done by including both routers in main import
router.include_router(legacy_router)


# ---------- v2 endpoints (preferred paths) ----------
@router.post("/start-session")
def start_session(payload: StartReq):
    sess = _new_session(role=payload.role or "general", question_count=payload.question_count or 5, difficulty=payload.difficulty or "Medium", resume_id=payload.resume_id)
    # Return a compact session summary
    first_q = sess["questions"][0] if sess["questions"] else None
    return {"status": "success", "data": {"session_id": sess["session_id"], "question": first_q["question_text"] if first_q else None, "role": sess["role"]}}


@router.post("/{session_id}/next")
def next_question(session_id: str):
    sess = _get_session(session_id)
    if sess["pointer"] >= len(sess["questions"]):
        return {"status": "completed", "data": {"message": "No more questions"}}
    q = sess["questions"][sess["pointer"]]
    # Send question (UI expects question_id and text + progress)
    return {
        "question_id": q["question_id"],
        "question_text": q["question_text"],
        "current_index": q["current_index"],
        "total_questions": q["total_questions"]
    }


@router.post("/submit-answer")
def submit_answer(payload: AnswerReq = Body(...)):
    sess = _get_session(payload.session_id)
    # If exchange_id provided, try to locate; else use pointer
    ptr = sess["pointer"]
    q = None
    if payload.exchange_id:
        for idx, qq in enumerate(sess["questions"]):
            if qq["question_id"] == payload.exchange_id:
                q = qq
                ptr = idx
                break
    if not q:
        if ptr >= len(sess["questions"]):
            raise HTTPException(status_code=400, detail="session completed")
        q = sess["questions"][ptr]

    # Evaluate deterministically (fallback). Later replace with LLM-driven evaluation.
    evaluation = deterministic_evaluate_answer(q["question_text"], payload.answer)

    # store
    sess["history"].append({
        "question_id": q["question_id"],
        "question": q["question_text"],
        "answer": payload.answer,
        "evaluation": evaluation,
        "timestamp": time.time()
    })

    # advance pointer if this was the expected question
    if ptr == sess["pointer"]:
        sess["pointer"] = sess["pointer"] + 1

    # prepare next question (if any)
    next_q = None
    if sess["pointer"] < len(sess["questions"]):
        nq = sess["questions"][sess["pointer"]]
        next_q = {
            "question_id": nq["question_id"],
            "question": nq["question_text"],
            "current_index": nq["current_index"],
            "total_questions": nq["total_questions"]
        }

    return {
        "status": "success",
        "data": {
            "evaluation": {
                "score": evaluation["score"],
                "strengths": evaluation["strengths"],
                "weaknesses": evaluation["weaknesses"],
                "feedback": evaluation["feedback"],
                "metrics": evaluation["metrics"]
            },
            "next_question": next_q,
            "session_id": sess["session_id"],
            "history_count": len(sess["history"])
        }
    }


@router.post("/{session_id}/end")
def finish_session(session_id: str):
    sess = _get_session(session_id)
    sess["finished"] = True
    # compute report: aggregate scores and provide quick items
    scores = [h["evaluation"]["score"] for h in sess["history"] if h.get("evaluation")]
    overall = int(round(sum(scores)/len(scores))) if scores else 0
    # quick wins / issues heuristics
    strengths = []
    issues = []
    for h in sess["history"]:
        ev = h.get("evaluation", {})
        for s in ev.get("strengths", []):
            strengths.append(s)
        for w in ev.get("weaknesses", []):
            issues.append(w)

    sess["report"] = {
        "overall_score": overall,
        "breakdown": {
            "communication": overall,  # placeholder
            "technical": overall,
            "structure": overall
        },
        "insights": {
            "good_points": list(dict.fromkeys(strengths))[:8],
            "issues": list(dict.fromkeys(issues))[:12],
            "overall_summary": f"Session completed. Average score {overall}."
        },
        "transcript": [{
            "question": h["question"],
            "user_answer": h["answer"],
            "feedback": h["evaluation"]["feedback"],
            "improved_answer": None  # placeholder for future LLM rewrite
        } for h in sess["history"]]
    }
    return {"status": "success", "data": {"session_id": session_id, "summary": sess["report"]}}


@router.get("/{session_id}/results")
def get_results(session_id: str):
    sess = _get_session(session_id)
    if not sess.get("report"):
        # if not yet finished, attempt a light finish
        finish_session(session_id)
    return {"status": "success", "data": sess["report"]}


# Expose a tiny health endpoint to check sessions count
@router.get("/_debug/sessions")
def debug_sessions():
    return {"count": len(SESSIONS), "sessions": list(SESSIONS.keys())}
