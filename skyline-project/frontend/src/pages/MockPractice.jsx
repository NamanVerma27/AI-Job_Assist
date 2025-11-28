// src/pages/MockPractice.jsx
import React, { useEffect, useState } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { motion } from "framer-motion";

import ChatTimeline from "../components/mock/ChatTimeline";
import SidebarStatus from "../components/mock/SidebarStatus";
import AnswerBar from "../components/mock/AnswerBar";
import TypingIndicator from "../components/mock/TypingIndicator";
import SidebarToggle from "../components/mock/SidebarToggle";
import MockResult from "./MockResult"; // Adjust path if needed

/**
 * MockPractice page
 * - mode: 'setup' | 'interview' | 'analyzing' | 'result'
 * - resilient API endpoints with fallback list
 */

const START_ENDPOINTS = [
  "/mock/start",
  "/api/mock/start",
  "/mock-v2/start-session",
  "/api/mock-v2/start-session"
];

const NEXT_ENDPOINTS = [
  "/mock/question",
  "/api/mock/question",
  "/mock/next",
  "/api/mock-v2/next"
];

const ANSWER_ENDPOINTS = [
  "/mock/answer",
  "/api/mock/answer",
  "/mock-v2/submit-answer",
  "/api/mock-v2/answer"
];

const END_ENDPOINTS = [
  "/mock/end",
  "/api/mock/end",
  "/mock-v2/end",
  "/api/mock-v2/finish"
];

const RESULTS_ENDPOINTS = (sessionId) => [
  `/mock/results/${sessionId}`,
  `/api/mock/results/${sessionId}`,
  `/mock-v2/${sessionId}/results`,
  `/api/mock-v2/${sessionId}/results`
];

export default function MockPractice() {
  const [mode, setMode] = useState("setup");
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [sessionId, setSessionId] = useState(null);

  const [sessionConfig, setSessionConfig] = useState({
    target_role: "",
    difficulty: "Medium",
    question_count: 5,
    resume_id: ""
  });

  const [resumes, setResumes] = useState([]);
  const [messages, setMessages] = useState([]);
  const [currentQ, setCurrentQ] = useState(null);
  const [isTyping, setIsTyping] = useState(false);
  const [report, setReport] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);

  // Helper to push chat messages (preserves order)
  const pushMessage = (msg) => setMessages((p) => [...p, msg]);

  // Load saved resumes (best-effort)
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const tryUrls = ["/api/profile/resumes", "/profile/resumes"];
        for (const url of tryUrls) {
          try {
            const res = await axios.get(url);
            const data = res.data?.data ?? res.data;
            if (mounted && Array.isArray(data)) {
              setResumes(data);
              break;
            }
          } catch (e) {
            // try next
          }
        }
      } catch (e) {
        // swallow
      }
    })();
    return () => (mounted = false);
  }, []);

  // -----------------------
  // Helpers: try endpoints
  // -----------------------
  async function tryPost(endpoints, payload = {}) {
    let lastErr = null;
    for (const ep of endpoints) {
      try {
        const res = await axios.post(ep, payload);
        if (res && (res.status >= 200 && res.status < 300)) return res.data;
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr || new Error("No endpoint reachable");
  }

  async function tryGet(endpoints) {
    let lastErr = null;
    const list = Array.isArray(endpoints) ? endpoints : [endpoints];
    for (const ep of list) {
      try {
        const res = await axios.get(ep);
        if (res && (res.status >= 200 && res.status < 300)) return res.data;
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr || new Error("No endpoint reachable");
  }

  // -----------------------
  // Start session
  // -----------------------
  const handleStartSession = async () => {
    if (!sessionConfig.target_role?.trim()) {
      return toast.error("Please enter a target role.");
    }
    setIsProcessing(true);
    try {
      const payload = {
        role: sessionConfig.target_role,
        difficulty: sessionConfig.difficulty,
        question_count: sessionConfig.question_count,
        resume_id: sessionConfig.resume_id || null
      };

      const data = await tryPost(START_ENDPOINTS, payload);

      // backend shapes differ — normalize
      const resp = data?.data ?? data;
      const sid = resp?.session_id || resp?.id || resp?.session || (resp && resp.session_id);
      const firstQ = resp?.question || resp?.question_text || resp?.question_text_full || null;

      if (!sid) {
        toast.error("Start session response missing session id.");
        console.debug("start response:", data);
        setIsProcessing(false);
        return;
      }

      setSessionId(sid);
      // Welcome message & first question
      pushMessage({ id: `sys-welcome-${Date.now()}`, type: "ai", text: `Interview initialized for ${sessionConfig.target_role}.` });
      if (firstQ) {
        setTimeout(() => pushMessage({ id: `q-${sid}-0`, type: "ai", text: firstQ }), 350);
        setCurrentQ({ question_id: resp?.question_id || null, question_text: firstQ, current_index: 1, total_questions: sessionConfig.question_count });
      }
      // switch into interview flow
      setMode("interview");
      setIsProcessing(false);
    } catch (err) {
      console.error("Start session error:", err);
      toast.error("Could not start session. Check backend.");
      setIsProcessing(false);
    }
  };

  // -----------------------
  // Fetch next question
  // -----------------------
  const fetchNextQuestion = async () => {
    if (!sessionId) return;
    setIsTyping(true);
    try {
      // Try POST-based next (session in body)
      const payload = { session_id: sessionId };
      let data = null;
      try {
        data = await tryPost(NEXT_ENDPOINTS, payload);
      } catch (e) {
        // Try GET style result endpoints
        const list = [`/mock/next/${sessionId}`, `/api/mock/next/${sessionId}`, `/mock-v2/${sessionId}/next`];
        try {
          data = await tryGet(list);
        } catch (e2) {
          throw e2;
        }
      }

      const body = data?.data ?? data;
      // If backend signals completion
      if (body?.status === "completed" || body?.completed === true) {
        setIsTyping(false);
        await generateReport();
        return;
      }

      const qtext = body?.question || body?.question_text || body?.question_text_full || null;
      const qid = body?.question_id || body?.id || null;
      const idx = body?.current_index || (currentQ?.current_index ? currentQ.current_index + 1 : 1);
      const total = body?.total_questions || sessionConfig.question_count;

      if (!qtext) {
        throw new Error("No question returned");
      }

      setTimeout(() => {
        pushMessage({ id: `q-${qid || Date.now()}`, type: "ai", text: qtext });
        setIsTyping(false);
      }, 700);

      setCurrentQ({
        question_id: qid,
        question_text: qtext,
        current_index: idx,
        total_questions: total
      });
    } catch (err) {
      console.error("Next question error:", err);
      setIsTyping(false);
      toast.error("Failed to fetch next question.");
    }
  };

  // -----------------------
  // Submit answer
  // -----------------------
  const handleSubmitAnswer = async (answerText) => {
    if (!currentQ || !sessionId) return toast.error("No active question.");
    // push user message
    pushMessage({ id: `u-${currentQ.question_id || Date.now()}`, type: "user", text: answerText });

    // Ask backend to evaluate
    setIsTyping(true);
    try {
      const payload = {
        session_id: sessionId,
        answer: answerText,
        question_id: currentQ.question_id
      };

      let data = null;
      try {
        data = await tryPost(ANSWER_ENDPOINTS, payload);
      } catch (e) {
        // fallback shapes
        const alt = { session_id: sessionId, answer_text: answerText, exchange_id: currentQ.question_id };
        data = await tryPost(ANSWER_ENDPOINTS, alt);
      }

      const body = data?.data ?? data;

      // Normalized feedback
      const feedbackText = body?.evaluation?.feedback || body?.feedback || body?.result || body?.comment || JSON.stringify(body);
      pushMessage({ id: `fb-${currentQ.question_id || Date.now()}`, type: "feedback", text: feedbackText });

      // continue to next question after small pause
      setTimeout(() => fetchNextQuestion(), 900);
    } catch (err) {
      console.error("Submit answer error:", err);
      setIsTyping(false);
      pushMessage({ id: `fb-err-${Date.now()}`, type: "feedback", text: "Could not evaluate answer — try again." });
    }
  };

  // -----------------------
  // End session & fetch report
  // -----------------------
  const generateReport = async () => {
    if (!sessionId) return toast.error("No session to end.");
    setMode("analyzing");
    setIsProcessing(true);

    // try posting end
    try {
      await tryPost(END_ENDPOINTS, { session_id: sessionId });
    } catch (e) {
      // ignore if unavailable
    }

    try {
      const resultsUrls = RESULTS_ENDPOINTS(sessionId);
      const data = await tryGet(resultsUrls);
      const body = data?.data ?? data;
      setReport(body);
      setMode("result");
    } catch (err) {
      console.error("Fetch results error:", err);
      toast.error("Could not fetch results. Try later.");
      // still show result mode with whatever we have
      setMode("result");
    } finally {
      setIsProcessing(false);
    }
  };

  // -----------------------
  // UI: restart
  // -----------------------
  const handleRestart = () => {
    setMode("setup");
    setSessionId(null);
    setCurrentQ(null);
    setMessages([]);
    setReport(null);
  };

  // -----------------------
  // Responsive sidebar auto behavior
  // -----------------------
  useEffect(() => {
    const onResize = () => {
      const small = window.innerWidth < 900;
      setSidebarOpen(!small); // open on desktop, closed on mobile
    };
    onResize();
    window.addEventListener("resize", onResize);
    return () => window.removeEventListener("resize", onResize);
  }, []);

  // -----------------------
  // Renders
  // -----------------------
  if (mode === "setup") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-indigo-100 p-6">
        <div className="bg-white rounded-3xl shadow-xl max-w-4xl w-full grid md:grid-cols-2">
          {/* Left Display */}
          <div className="p-10 bg-indigo-600 text-white rounded-l-3xl flex flex-col justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-4">Mock Interview</h1>
              <p className="text-indigo-200 text-lg">Practice role-specific interview questions with instant AI feedback.</p>
            </div>

            <ul className="space-y-3 mt-10 text-indigo-100">
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                Role-adaptive questions
              </li>
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                Micro-feedback & rewrite suggestions
              </li>
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                End-of-session performance report
              </li>
            </ul>
          </div>

          {/* Form Side */}
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

              <div>
                <label className="font-bold text-gray-700">Difficulty</label>
                <select
                  className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.difficulty}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, difficulty: e.target.value })}
                >
                  <option>Easy</option>
                  <option>Medium</option>
                  <option>Hard</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-gray-700">Number of Questions</label>
                <select
                  className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.question_count}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, question_count: parseInt(e.target.value) })}
                >
                  <option value={3}>3 (Quick)</option>
                  <option value={5}>5 (Standard)</option>
                  <option value={8}>8 (Deep)</option>
                </select>
              </div>

              <div>
                <label className="font-bold text-gray-700">Use Resume (optional)</label>
                <select
                  className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.resume_id}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, resume_id: e.target.value })}
                >
                  <option value="">None</option>
                  {resumes.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.filename}
                    </option>
                  ))}
                </select>
              </div>

              <button
                onClick={handleStartSession}
                disabled={isProcessing}
                className="mt-4 w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-lg hover:bg-indigo-700 disabled:opacity-60"
              >
                {isProcessing ? "Starting…" : "Start Interview"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (mode === "interview") {
    return (
      <div className="min-h-screen flex bg-gray-50">
        {/* Sidebar (auto-hide on mobile) */}
        <motion.aside
          initial={{ x: -20, opacity: 0 }}
          animate={{ x: 0, opacity: 1 }}
          className={`hidden md:flex z-20`}
          style={{ width: sidebarOpen ? 288 : 88 }}
        >
          <SidebarStatus
            currentIndex={currentQ?.current_index || 0}
            total={currentQ?.total_questions || sessionConfig.question_count}
            difficulty={sessionConfig.difficulty}
            role={sessionConfig.target_role}
          />
        </motion.aside>

        {/* Small toggle for mobile and collapse */}
        <SidebarToggle open={sidebarOpen} setOpen={setSidebarOpen} />

        {/* Chat area */}
        <div className="flex-grow flex flex-col">
          <div className="flex items-center justify-between px-6 py-4 bg-white border-b shadow-sm">
            <div>
              <div className="text-sm text-gray-500">Interviewing for</div>
              <div className="font-semibold text-lg">{sessionConfig.target_role}</div>
            </div>

            <div className="flex items-center gap-3">
              <div className="text-sm text-gray-500">Question</div>
              <div className="font-medium">{currentQ?.current_index || 0}/{currentQ?.total_questions || sessionConfig.question_count}</div>
              <button className="text-sm text-red-600" onClick={() => { if (confirm("End session and get report?")) generateReport(); }}>
                End & Report
              </button>
            </div>
          </div>

          <div className="flex-grow overflow-y-auto p-8 pb-36">
            <ChatTimeline messages={messages} />
            {isTyping && <TypingIndicator />}
          </div>

          <AnswerBar onSubmit={handleSubmitAnswer} />
        </div>
      </div>
    );
  }

  if (mode === "analyzing") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center bg-gray-50">
        <div className="w-20 h-20 border-4 border-indigo-200 border-t-indigo-600 animate-spin rounded-full"></div>
        <h2 className="text-2xl font-bold mt-6 text-gray-700">Generating your interview report…</h2>
        <p className="text-gray-500 mt-2">Evaluating technical depth, clarity, structure and impact.</p>
      </div>
    );
  }

  if (mode === "result") {
    // Basic result view — if report is missing show fallback
    return (
      <div className="min-h-screen p-10 bg-gray-50">
        <div className="max-w-4xl mx-auto bg-white rounded-3xl shadow-xl p-8">
          <div className="flex items-start justify-between gap-6">
            <div>
              <h2 className="text-2xl font-bold">Interview Report</h2>
              <p className="text-gray-600 mt-1">Summary of your session and targeted improvements.</p>
            </div>

            <div className="flex items-center gap-3">
              <button className="px-4 py-2 rounded-lg border" onClick={handleRestart}>Run Another</button>
              <button className="px-4 py-2 rounded-lg bg-indigo-600 text-white" onClick={() => { navigator.clipboard.writeText(JSON.stringify(report || {}, null, 2)); toast.success("Copied report"); }}>Copy JSON</button>
            </div>
          </div>

          <div className="mt-6 space-y-4">
            {/* If you have a nicer MockResult component, you can swap this to:
                <MockResult report={report} onRestart={handleRestart} /> */}
            {report ? (
              <MockResult report={report} onRestart={handleRestart} />
            ) : (
              <pre className="bg-gray-50 p-4 rounded text-sm overflow-auto">{JSON.stringify({ message: "No report available" }, null, 2)}</pre>
            )}
          </div>
        </div>
      </div>
    );
  }

  return null;
}
