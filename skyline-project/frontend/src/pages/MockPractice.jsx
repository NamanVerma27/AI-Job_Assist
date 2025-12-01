// src/pages/MockPractice.jsx
import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { FaPlay } from "react-icons/fa";
import { useNavigate } from "react-router-dom";

import ChatTimeline from "../components/mock/ChatTimeline";
import SidebarStatus from "../components/mock/SidebarStatus";
import AnswerBar from "../components/mock/AnswerBar";
import TypingIndicator from "../components/mock/TypingIndicator";

/**
 * MockPractice.jsx
 *
 * Features:
 * - Setup screen (role, difficulty, question count, optional resume)
 * - Intro screen (confirm & start)
 * - Interview loop (fetch question -> user answer -> evaluate -> next)
 * - Analyzing -> navigates to MockResult (report saved to sessionStorage)
 *
 * Endpoints (tries multiple fallbacks):
 * - Start:     POST /mock/start  OR  POST /api/mock-v2/start-session
 * - Next Q:    POST /mock/question OR POST /api/mock-v2/{session}/next
 * - Answer:    POST /mock/answer   OR POST /api/mock-v2/submit-answer
 * - End/Report: POST /mock/end + GET /mock/result  OR POST /api/mock-v2/{session}/end + GET /api/mock-v2/{session}/results
 *
 * This component is defensive about response shapes and will show toast errors when network calls fail.
 */

export default function MockPractice() {
  const navigate = useNavigate();

  // Modes: 'setup' | 'intro' | 'interview' | 'analyzing'
  const [mode, setMode] = useState("setup");

  // Config & resources
  const [sessionConfig, setSessionConfig] = useState({
    target_role: "",
    difficulty: "Medium",
    question_count: 5,
    resume_id: ""
  });
  const [resumes, setResumes] = useState([]);

  // Interview state
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]); // {id, type: 'ai'|'user'|'feedback', text}
  const [currentQ, setCurrentQ] = useState(null); // normalized {question_id, question_text, current_index, total_questions}
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // Report placeholder (kept in sessionStorage on finish)
  const [report, setReport] = useState(null);

  const mountedRef = useRef(true);
  useEffect(() => {
    return () => {
      mountedRef.current = false;
    };
  }, []);

  // load resumes (non-critical)
  useEffect(() => {
    (async () => {
      try {
        const tryUrls = ["/api/profile/resumes", "/profile/resumes"];
        for (const url of tryUrls) {
          try {
            const res = await axios.get(url);
            const payload = res?.data?.data ?? res?.data;
            if (Array.isArray(payload)) {
              setResumes(payload);
              break;
            }
          } catch {
            // try next
          }
        }
      } catch {
        /* ignore */
      }
    })();
  }, []);

  // UI helper: push a timeline message
  const pushMessage = (msg) => setMessages((prev) => [...prev, msg]);

  // --- Endpoint helpers (try multiple endpoints/fallbacks) ---
  const startSessionRequest = async (cfg) => {
    const payload = {
      role: cfg.target_role,
      difficulty: cfg.difficulty,
      question_count: cfg.question_count,
      resume_id: cfg.resume_id || null
    };

    const attempts = [
      { method: "post", url: "/mock/start", data: payload },
      { method: "post", url: "/api/mock-v2/start-session", data: payload },
      { method: "post", url: "/mock-v2/start-session", data: payload },
    ];

    for (const a of attempts) {
      try {
        const r = await axios[a.method](a.url, a.data);
        // Normalize response shape: prefer r.data.data or r.data
        const body = r?.data?.data ?? r?.data;
        if (body) return body;
      } catch (e) {
        // continue
      }
    }
    throw new Error("No start endpoint reachable");
  };

  const fetchNextQuestionRequest = async (sid) => {
    const attempts = [
      { method: "post", url: "/mock/question", data: { session_id: sid } },
      { method: "post", url: `/mock-v2/${sid}/next`, data: {} },
      { method: "post", url: `/api/mock-v2/${sid}/next`, data: {} },
    ];

    for (const a of attempts) {
      try {
        const r = await axios[a.method](a.url, a.data);
        const body = r?.data?.data ?? r?.data;
        if (body) return body;
      } catch (e) {}
    }
    throw new Error("No next-question endpoint reachable");
  };

  const submitAnswerRequest = async (sid, exchangeId, answerText) => {
    const attempts = [
      { method: "post", url: "/mock/answer", data: { session_id: sid, answer: answerText } },
      { method: "post", url: "/mock/answer", data: { session_id: sid, answer_text: answerText } }, // older variations
      { method: "post", url: "/api/mock-v2/submit-answer", data: { exchange_id: exchangeId, user_answer: answerText } },
      { method: "post", url: "/mock-v2/submit-answer", data: { exchange_id: exchangeId, user_answer: answerText } },
    ];

    for (const a of attempts) {
      try {
        const r = await axios[a.method](a.url, a.data);
        const body = r?.data?.data ?? r?.data;
        if (body) return body;
      } catch (e) {}
    }
    throw new Error("No submit-answer endpoint reachable");
  };

  const endSessionAndFetchReport = async (sid) => {
    const attempts = [
      { method: "post", url: "/mock/end", data: { session_id: sid } },
      { method: "post", url: `/mock-v2/${sid}/end`, data: {} },
      { method: "post", url: `/api/mock-v2/${sid}/end`, data: {} },
    ];
    // try to call end first (best-effort)
    for (const a of attempts) {
      try {
        await axios[a.method](a.url, a.data);
        break;
      } catch (e) {}
    }

    // fetch result
    const fetches = [
      { method: "get", url: "/mock/result" },
      { method: "get", url: `/mock-v2/${sid}/results` },
      { method: "get", url: `/api/mock-v2/${sid}/results` },
    ];
    for (const f of fetches) {
      try {
        const r = await axios[f.method](f.url);
        const body = r?.data?.data ?? r?.data;
        if (body) return body;
      } catch (e) {}
    }
    throw new Error("No results endpoint reachable");
  };

  // --- Flow actions ---
  const handleStartSession = async () => {
    if (!sessionConfig.target_role || !sessionConfig.target_role.trim()) {
      toast.error("Please enter a target role.");
      return;
    }

    setIsLoading(true);
    setMessages([]);
    setCurrentQ(null);
    setSessionId(null);

    try {
      const resp = await startSessionRequest(sessionConfig);
      // possible shapes:
      // { session_id, question, role }  OR { id, first_question... } OR whole session object
      const sid = resp.session_id ?? resp.id ?? resp.session?.id ?? null;
      const firstQuestionText = resp.question ?? resp.first_question ?? resp.question_text ?? (resp.data && resp.data.question);
      setSessionId(sid);
      // If server returned an opening question, push to timeline and also set currentQ
      if (firstQuestionText) {
        const qid = resp.question_id ?? resp.question_id ?? `q-${Date.now()}`;
        const normalized = {
          question_id: qid,
          question_text: firstQuestionText,
          current_index: 1,
          total_questions: sessionConfig.question_count
        };
        setCurrentQ(normalized);
        pushMessage({ id: `q-${qid}`, type: "ai", text: firstQuestionText });
      }
      // move to intro briefly for UX, then interview
      setMode("intro");
      setTimeout(() => setMode("interview"), 800);
      toast.success("Session started");
    } catch (err) {
      console.error("Start session failed:", err);
      toast.error("Could not start session. Check backend.");
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  };

  // fetch next question and show typing indicator
  const fetchNextQuestion = async () => {
    if (!sessionId) {
      toast.error("No active session.");
      return;
    }
    setIsTyping(true);
    setIsLoading(true);
    try {
      const resp = await fetchNextQuestionRequest(sessionId);
      // If server signals completed
      if (resp.status === "completed" || resp.completed === true || resp.done === true) {
        // generate final report
        await handleFinishSession();
        return;
      }

      // Normalize question
      const qtext = resp.question_text ?? resp.question ?? resp.q ?? resp.question_text;
      const qid = resp.question_id ?? resp.id ?? `q-${Date.now()}`;
      const normalized = {
        question_id: qid,
        question_text: qtext,
        current_index: resp.current_index ?? (currentQ ? (currentQ.current_index + 1) : 1),
        total_questions: resp.total_questions ?? sessionConfig.question_count
      };
      setTimeout(() => {
        pushMessage({ id: `q-${qid}`, type: "ai", text: qtext });
        setCurrentQ(normalized);
        setIsTyping(false);
      }, 600); // small delay for UX
    } catch (err) {
      console.error("Next question failed:", err);
      setIsTyping(false);
      toast.error("Could not fetch next question.");
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  };

  const handleSubmitAnswer = async (answerText) => {
    if (!currentQ) {
      toast.error("No active question.");
      return;
    }
    if (!answerText || !answerText.trim()) {
      toast.error("Please type an answer before submitting.");
      return;
    }

    // push user message to timeline
    pushMessage({ id: `u-${currentQ.question_id}`, type: "user", text: answerText });

    setIsLoading(true);
    setIsTyping(true);

    try {
      const resp = await submitAnswerRequest(sessionId, currentQ.question_id, answerText);

      // resp likely contains evaluation and next_question
      // shapes seen: { evaluation: {...}, next_question: {...}, session_id, history_count }
      const evaluation = resp.evaluation ?? resp.feedback ?? resp.result ?? (resp.data && resp.data.evaluation) ?? null;
      const feedbackText = evaluation?.feedback ?? evaluation?.score ? `Score: ${evaluation.score}` : (resp.feedback_text || resp.message || (evaluation && JSON.stringify(evaluation)));

      // push feedback micro message
      pushMessage({ id: `fb-${currentQ.question_id}`, type: "feedback", text: feedbackText || "Feedback received." });

      // if server supplied next question inline, use it, otherwise call next
      const nextQ = resp.next_question ?? resp.next ?? resp.question ?? null;
      if (nextQ && (nextQ.question || nextQ.question_text || nextQ.question_id)) {
        const qtext = nextQ.question_text ?? nextQ.question ?? nextQ.q;
        const qid = nextQ.question_id ?? nextQ.id ?? `q-${Date.now()}`;
        const normalized = {
          question_id: qid,
          question_text: qtext,
          current_index: nextQ.current_index ?? (currentQ.current_index + 1),
          total_questions: nextQ.total_questions ?? sessionConfig.question_count
        };
        setTimeout(() => {
          pushMessage({ id: `q-${qid}`, type: "ai", text: qtext });
          setCurrentQ(normalized);
          setIsTyping(false);
        }, 800);
      } else {
        // call server for next question (server may manage sequence)
        setTimeout(() => {
          setIsTyping(false);
          fetchNextQuestion();
        }, 900);
      }
    } catch (err) {
      console.error("Submit answer failed:", err);
      pushMessage({ id: `fb-${currentQ.question_id}`, type: "feedback", text: "Evaluation failed. Try next question." });
      setIsTyping(false);
      toast.error("Answer submission failed.");
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  };

  // finish and fetch report, then navigate to results page
  const handleFinishSession = async () => {
    if (!sessionId) {
      toast.error("No active session to finalize.");
      return;
    }
    setMode("analyzing");
    setIsLoading(true);
    try {
      const rpt = await endSessionAndFetchReport(sessionId);
      // Save in session storage for MockResult to pick up (and for page reload)
      try {
        sessionStorage.setItem("mock_report", JSON.stringify(rpt));
      } catch {}
      setReport(rpt);
      // navigate to MockResult page (ensure route exists)
      navigate("/mock-result", { state: { report: rpt } });
    } catch (err) {
      console.error("Finish session failed:", err);
      toast.error("Could not generate final report.");
      // still attempt to navigate with whatever we have
      try {
        const maybeSaved = sessionStorage.getItem("mock_report");
        if (maybeSaved) {
          navigate("/mock-result");
        } else {
          setMode("setup");
        }
      } catch {
        setMode("setup");
      }
    } finally {
      if (mountedRef.current) setIsLoading(false);
    }
  };

  // UI renderers
  if (mode === "setup") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-indigo-100 p-6">
        <div className="bg-white rounded-3xl shadow-xl max-w-4xl w-full grid md:grid-cols-2">
          <div className="p-10 bg-indigo-600 text-white rounded-l-3xl flex flex-col justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-4">Mock Interview</h1>
              <p className="text-indigo-200 text-lg">Practice real interview questions with AI-driven feedback.</p>
            </div>
            <ul className="space-y-3 mt-10 text-indigo-100">
              <li>Role-specific adaptive questions</li>
              <li>Real-time micro-feedback</li>
              <li>Final performance report</li>
            </ul>
          </div>

          <div className="p-10">
            <h2 className="text-2xl font-bold mb-6">Configure Interview</h2>

            <div className="space-y-6">
              <div>
                <label className="font-bold text-gray-700">Target Role</label>
                <input
                  className="mt-2 w-full p-3 border rounded-xl"
                  placeholder="e.g. Frontend Developer"
                  value={sessionConfig.target_role}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, target_role: e.target.value })}
                />
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="font-bold text-gray-700">Difficulty</label>
                  <select className="mt-2 w-full p-3 border rounded-xl" value={sessionConfig.difficulty} onChange={(e) => setSessionConfig({ ...sessionConfig, difficulty: e.target.value })}>
                    <option>Easy</option>
                    <option>Medium</option>
                    <option>Hard</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-gray-700">Number of Questions</label>
                  <select className="mt-2 w-full p-3 border rounded-xl" value={sessionConfig.question_count} onChange={(e) => setSessionConfig({ ...sessionConfig, question_count: parseInt(e.target.value) })}>
                    <option value="3">3 (Quick)</option>
                    <option value="5">5 (Standard)</option>
                    <option value="8">8 (Deep)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-gray-700">Use Resume? (optional)</label>
                {resumes.length ? (
                  <select className="mt-2 w-full p-3 border rounded-xl" value={sessionConfig.resume_id} onChange={(e) => setSessionConfig({ ...sessionConfig, resume_id: e.target.value })}>
                    <option value="">None</option>
                    {resumes.map((r) => <option key={r.id} value={r.id}>{r.filename}</option>)}
                  </select>
                ) : (
                  <div className="mt-2 p-3 bg-gray-50 rounded-xl text-sm text-gray-500 border border-dashed">No uploaded resumes found. You can proceed without one.</div>
                )}
              </div>

              <button onClick={handleStartSession} className="mt-4 w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-lg hover:bg-indigo-700 flex items-center justify-center gap-2">
                <FaPlay /> Start Interview
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "intro") {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex items-center justify-center p-6 text-center">
        <div className="max-w-xl">
          <div className="w-20 h-20 bg-indigo-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl">AI</div>
          <h1 className="text-4xl font-bold mb-4">Get Ready!</h1>
          <p className="text-xl text-gray-300 mb-8">You are about to start a <strong>{sessionConfig.difficulty}</strong> interview for <strong>{sessionConfig.target_role}</strong>.</p>
          <button className="px-10 py-4 bg-white text-indigo-900 font-bold rounded-full text-lg hover:scale-105 transition shadow-lg" onClick={() => { setMode("interview"); /* if server returned first question already, we will show it, else fetch next */ if (!currentQ) setTimeout(() => fetchNextQuestion(), 350); }}>
            Start Interview
          </button>
        </div>
      </div>
    );
  }

  if (mode === "interview") {
    return (
      <div className="min-h-screen bg-gray-50 flex">
        <SidebarStatus
          currentIndex={currentQ?.current_index ?? 0}
          total={currentQ?.total_questions ?? sessionConfig.question_count}
          difficulty={sessionConfig.difficulty}
          role={sessionConfig.target_role}
        />

        <div className="flex-grow flex flex-col">
          <div className="flex-grow overflow-y-auto p-8 pb-32">
            <ChatTimeline messages={messages} />
            {isTyping && <TypingIndicator />}
          </div>

          <AnswerBar
            onSubmit={(text) => handleSubmitAnswer(text)}
            placeholder={isLoading ? "Processing..." : "Type your answer... (Shift+Enter for newline)"}
          />
        </div>
      </div>
    );
  }

  // analyzing is short-lived (we navigate to MockResult after fetching)
  if (mode === "analyzing") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center bg-gray-50 p-6">
        <div className="w-20 h-20 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-6"></div>
        <h2 className="text-2xl font-bold text-gray-700">Generating your interview report…</h2>
        <p className="text-gray-500 mt-2">We are compiling scores, suggested improvements and an overall summary.</p>
      </div>
    );
  }

  // fallback
  return null;
}
