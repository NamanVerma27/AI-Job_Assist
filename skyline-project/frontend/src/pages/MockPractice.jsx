// src/pages/MockPractice.jsx
import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { motion } from "framer-motion";

import ChatTimeline from "../components/mock/ChatTimeline";
import SidebarStatus from "../components/mock/SidebarStatus";
import AnswerBar from "../components/mock/AnswerBar";
import TypingIndicator from "../components/mock/TypingIndicator";
import MockResult from "../components/mock/MockResult";
import "../components/mock/mock_result.css"; // ensures confetti/pulse styles are available

function MockPractice() {
  // Modes: 'setup' | 'intro' | 'interview' | 'analyzing' | 'result'
  const [mode, setMode] = useState("setup");

  // session config
  const [sessionConfig, setSessionConfig] = useState({
    target_role: "",
    difficulty: "Medium",
    question_count: 5,
    resume_id: ""
  });

  const [resumes, setResumes] = useState([]);

  // session runtime
  const [sessionId, setSessionId] = useState(null);
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [messages, setMessages] = useState([]); // [{id, type, text}]
  const [isTyping, setIsTyping] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  // results
  const [report, setReport] = useState(null);

  const timelineRef = useRef(null);

  // Load saved resumes for optional personalization
  useEffect(() => {
    let mounted = true;
    axios.get("/profile/resumes")
      .then((res) => {
        if (!mounted) return;
        const payload = res?.data ?? [];
        // Normalize — ensure an array is set
        setResumes(Array.isArray(payload) ? payload : (payload && payload.data && Array.isArray(payload.data) ? payload.data : []));
      })
      .catch((err) => {
        // silent fallback, but keep resumes as array
        console.debug("[MockPractice] could not load resumes", err?.message || err);
        setResumes([]);
      });
    return () => { mounted = false; };
  }, []);

  // Small helper to push chat messages
  const pushMessage = (msg) => setMessages(prev => [...prev, msg]);

  // ----------------------------
  // START SESSION
  // ----------------------------
  const startSession = async () => {
    if (!sessionConfig.target_role || sessionConfig.target_role.trim() === "") {
      toast.error?.("Target role is required") || alert("Target role is required");
      return;
    }

    try {
      setIsLoading(true);
      const payload = {
        target_role: sessionConfig.target_role,
        difficulty: sessionConfig.difficulty,
        question_count: sessionConfig.question_count,
        resume_id: sessionConfig.resume_id || null
      };

      const res = await axios.post("/mock-v2/start-session", payload);
      const data = (res.data && (res.data.data || res.data)) || {};
      const sid = data.session_id || data.id || data.sessionId || null;
      if (!sid) {
        console.warn("[startSession] no session id returned", res.data);
        toast.error("Failed to start session (no session id returned)");
        return;
      }
      setSessionId(sid);

      // initial first question (the start endpoint often returns a question)
      if (data.question) {
        const qObj = {
          question_id: data.question_id || `q-0`,
          question_text: data.question,
          current_index: data.current_index || 1,
          total_questions: data.total_questions || sessionConfig.question_count
        };
        setCurrentQuestion(qObj);
        pushMessage({ id: qObj.question_id, type: "ai", text: qObj.question_text });
      }

      // go to intro — then interview on user click
      setMode("intro");
    } catch (err) {
      console.error("startSession error", err?.response?.data || err.message || err);
      toast.error?.("Failed to start session");
    } finally {
      setIsLoading(false);
    }
  };

  const beginInterview = () => {
    setMode("interview");
    // If no current question preloaded, fetch next
    if (!currentQuestion) {
      fetchNextQuestion();
    }
  };

  // ----------------------------
  // FETCH NEXT QUESTION
  // ----------------------------
  const fetchNextQuestion = async () => {
    if (!sessionId) {
      toast.error?.("Session not started");
      return;
    }
    setIsTyping(true);
    setCurrentQuestion(null);

    try {
      const res = await axios.post(`/mock-v2/${sessionId}/next`);
      const payload = (res.data && (res.data.data || res.data)) || {};

      if (payload.status === "completed" || payload === "completed") {
        // backend suggests finished — generate final report
        await generateReport();
        return;
      }

      // expected shape: { question_id, question, current_index, total_questions }
      const q = {
        question_id: payload.question_id || payload.questionId || `q-${Date.now()}`,
        question_text: payload.question || payload.question_text || payload.question_text || "",
        current_index: payload.current_index || payload.currentIndex || 1,
        total_questions: payload.total_questions || payload.totalQuestions || sessionConfig.question_count
      };

      setCurrentQuestion(q);

      // small typing delay then push message
      setTimeout(() => {
        if (q.question_text) pushMessage({ id: `q-${q.question_id}`, type: "ai", text: q.question_text });
        else pushMessage({ id: `q-${q.question_id}`, type: "ai", text: "Question unavailable" });
        setIsTyping(false);
      }, 700);

    } catch (err) {
      console.error("fetchNextQuestion error", err?.response?.data || err.message || err);
      toast.error?.("Failed to fetch next question");
      setIsTyping(false);
    }
  };

  // ----------------------------
  // SUBMIT ANSWER
  // ----------------------------
  const handleSubmitAnswer = async (answerText) => {
    if (!currentQuestion) {
      toast.error?.("No active question");
      return;
    }

    const exchange_id = currentQuestion.question_id;
    // push user's message to timeline
    pushMessage({ id: `u-${exchange_id}`, type: "user", text: answerText });

    // call submit
    try {
      setIsLoading(true);
      const res = await axios.post("/mock-v2/submit-answer", {
        session_id: sessionId,
        exchange_id: exchange_id,
        answer: answerText
      });

      const payload = (res.data && (res.data.data || res.data)) || {};

      // feedback might be string or object
      const fbText = payload?.evaluation?.feedback || payload?.feedback || payload?.evaluation?.message || payload?.message || "Feedback unavailable";

      // push feedback block
      pushMessage({ id: `fb-${exchange_id}`, type: "feedback", text: fbText });

      // schedule fetch next question (or results if finished)
      const next = payload?.next_question || payload?.nextQuestion || null;

      if (next && (next.question || next.question_text)) {
        // small delay to let user read feedback
        setTimeout(() => {
          const nq = next;
          setCurrentQuestion({
            question_id: nq.question_id || nq.questionId,
            question_text: nq.question || nq.question_text || nq.questionText || "",
            current_index: nq.current_index || nq.currentIndex || 1,
            total_questions: nq.total_questions || nq.totalQuestions || sessionConfig.question_count
          });
          pushMessage({ id: `q-${nq.question_id || Date.now()}`, type: "ai", text: nq.question || nq.question_text || "" });
        }, 900);
      } else if (next === "completed" || payload?.status === "completed") {
        // session complete
        await generateReport();
      } else if (payload?.session_id && (payload.history_count >= (sessionConfig.question_count || 1))) {
        // if backend gives history_count reaching target, finalize
        await generateReport();
      } else {
        // default fallback: try to fetch next question after a small pause
        setTimeout(() => fetchNextQuestion(), 900);
      }

    } catch (err) {
      console.error("submit-answer error", err?.response?.data || err.message || err);
      const detail = err?.response?.data || err?.message;
      // show a helpful message if it's a 404 / session not found
      if (err?.response?.status === 404) {
        toast.error("Session not found. Please restart.");
        handleRestart();
      } else {
        toast.error?.("Failed to submit answer");
      }
    } finally {
      setIsLoading(false);
    }
  };

  // ----------------------------
  // GENERATE FINAL REPORT
  // ----------------------------
  const generateReport = async () => {
    if (!sessionId) return;

    setMode("analyzing");
    setIsLoading(true);

    try {
      // Trigger end on server (some implementations require it)
      try {
        await axios.post(`/mock-v2/${sessionId}/end`);
      } catch (e) {
        // non-fatal: some versions return 404 if already finished — continue
        console.debug("[generateReport] end() call non-fatal:", e?.response?.status || e?.message);
      }

      const res = await axios.get(`/mock-v2/${sessionId}/results`);
      const payload = (res.data && (res.data.data || res.data)) || {};
      setReport(payload);
      setMode("result");
    } catch (err) {
      console.error("generateReport error", err?.response?.data || err.message || err);
      toast.error?.("Scoring failed. Try again.");
      setMode("result");
      setReport(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleRestart = () => {
    setMode("setup");
    setSessionId(null);
    setCurrentQuestion(null);
    setMessages([]);
    setReport(null);
    setIsTyping(false);
  };

  // ----------------------------
  // UI RENDERS
  // ----------------------------
  if (mode === "setup") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-indigo-100 p-6">
        <div className="bg-white rounded-3xl shadow-xl max-w-4xl w-full grid md:grid-cols-2">
          <div className="p-10 bg-indigo-600 text-white rounded-l-3xl flex flex-col justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-4">Mock Interview</h1>
              <p className="text-indigo-200 text-lg">Practice real interview questions with AI.</p>
            </div>

            <ul className="space-y-3 mt-10 text-sm">
              <li className="flex items-center gap-3"><span className="w-3 h-3 bg-white rounded-full"></span> Role-specific adaptive questions</li>
              <li className="flex items-center gap-3"><span className="w-3 h-3 bg-white rounded-full"></span> Real-time AI micro-feedback</li>
              <li className="flex items-center gap-3"><span className="w-3 h-3 bg-white rounded-full"></span> Full performance report at the end</li>
            </ul>
          </div>

          <div className="p-10">
            <h2 className="text-2xl font-bold mb-6">Configure Session</h2>

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
                  <select className="mt-2 w-full p-3 border rounded-xl"
                    value={sessionConfig.difficulty}
                    onChange={(e) => setSessionConfig({ ...sessionConfig, difficulty: e.target.value })}>
                    <option>Easy</option><option>Medium</option><option>Hard</option>
                  </select>
                </div>

                <div>
                  <label className="font-bold text-gray-700">Number of Questions</label>
                  <select className="mt-2 w-full p-3 border rounded-xl"
                    value={sessionConfig.question_count}
                    onChange={(e) => setSessionConfig({ ...sessionConfig, question_count: parseInt(e.target.value) })}>
                    <option value="3">3 (Quick)</option>
                    <option value="5">5 (Standard)</option>
                    <option value="8">8 (Deep)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="font-bold text-gray-700">Use Resume? (Optional)</label>
                <select className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.resume_id}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, resume_id: e.target.value })}>
                  <option value="">None</option>
                  {resumes && resumes.length > 0 ? resumes.map((r) => (
                    <option key={r.id} value={r.id}>{r.filename}</option>
                  )) : <option disabled>No resumes available</option>}
                </select>
              </div>

              <button onClick={startSession}
                className="mt-4 w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-lg hover:bg-indigo-700">
                {isLoading ? "Starting..." : "Start Interview"}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // INTRO
  if (mode === "intro") {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-6 text-center">
        <motion.div initial={{ scale: 0.98, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="max-w-xl">
          <div className="w-20 h-20 bg-indigo-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl">AI</div>
          <h1 className="text-4xl font-bold mb-4">Get Ready!</h1>
          <p className="text-xl text-gray-300 mb-8">You are about to start a <strong>{sessionConfig.difficulty}</strong> interview for <strong>{sessionConfig.target_role}</strong>.</p>
          <button onClick={beginInterview} className="px-10 py-4 bg-white text-indigo-900 font-bold rounded-full text-lg hover:scale-105 transition shadow-lg">
            Start Interview
          </button>
        </motion.div>
      </div>
    );
  }

  // INTERVIEW (chat-like)
  if (mode === "interview") {
    return (
      <div className="min-h-screen flex bg-gray-50">
        <SidebarStatus
          currentIndex={currentQuestion?.current_index || 0}
          total={currentQuestion?.total_questions || sessionConfig.question_count}
          difficulty={sessionConfig.difficulty}
          role={sessionConfig.target_role}
        />

        <div className="flex-grow flex flex-col">
          <div className="flex-grow overflow-y-auto p-8 pb-40" ref={timelineRef}>
            <ChatTimeline messages={messages} />
            {isTyping && <TypingIndicator />}
          </div>

          <AnswerBar onSubmit={handleSubmitAnswer} placeholder="Type your answer..." isLoading={isLoading}/>
        </div>
      </div>
    );
  }

  // ANALYZING (waiting for report)
  if (mode === "analyzing") {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center">
        <div className="w-24 h-24 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-6"></div>
        <h2 className="text-2xl font-bold text-gray-800">Generating Performance Report...</h2>
        <p className="text-gray-500 mt-2">AI is rewriting your answers and calculating scores.</p>
      </div>
    );
  }

  // RESULT
  if (mode === "result") {
    return (
      <div className="min-h-screen bg-gray-50 p-6 md:p-10">
        <MockResult report={report || {}} onRestart={handleRestart} />
      </div>
    );
  }

  return null;
}

export default MockPractice;
