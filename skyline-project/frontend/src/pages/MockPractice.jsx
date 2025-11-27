import React, { useEffect, useState, useRef } from "react";
import axios from "axios";
import toast from "react-hot-toast";
import { motion } from "framer-motion";

import ChatTimeline from "../components/mock/ChatTimeline";
import SidebarStatus from "../components/mock/SidebarStatus";
import AnswerBar from "../components/mock/AnswerBar";
import TypingIndicator from "../components/mock/TypingIndicator";

function MockPractice() {
  const [mode, setMode] = useState("setup"); 
  const [sessionId, setSessionId] = useState(null);

  const [sessionConfig, setSessionConfig] = useState({
    target_role: "",
    difficulty: "Medium",
    question_count: 5,
    resume_id: ""
  });

  const [resumes, setResumes] = useState([]);

  // Interview state (chat style)
  const [messages, setMessages] = useState([]);
  const [currentQ, setCurrentQ] = useState(null);
  const [isTyping, setIsTyping] = useState(false);

  // Report
  const [report, setReport] = useState(null);

  // Load resumes
  useEffect(() => {
    axios.get("/api/profile/resumes")
      .then(res => setResumes(res.data || []))
      .catch(() => {});
  }, []);

  // UTIL: Add message to timeline
  const pushMessage = (msg) => {
    setMessages(prev => [...prev, msg]);
  };

  // ===================================
  // STEP 1 — START SESSION
  // ===================================
  const handleStartSession = async () => {
    if (!sessionConfig.target_role) return toast.error("Target role is required");
    try {
      const res = await axios.post("/api/mock-v2/start-session", {
        ...sessionConfig,
        resume_id: sessionConfig.resume_id || null
      });
      setSessionId(res.data.id);
      setMode("intro");
      setTimeout(() => setMode("interview"), 1200);
    } catch (err) {
      toast.error("Failed to start");
    }
  };

  // ===================================
  // STEP 2 — FETCH NEXT QUESTION
  // ===================================
  const fetchNextQuestion = async () => {
    setIsTyping(true);

    try {
      const res = await axios.post(`/api/mock-v2/${sessionId}/next`);
      
      if (res.data.status === "completed") {
        await generateReport();
        return;
      }

      const q = res.data;
      setCurrentQ(q);

      setTimeout(() => {
        pushMessage({
          id: "q-" + q.question_id,
          type: "ai",
          text: q.question_text,
        });
        setIsTyping(false);
      }, 900);

    } catch (err) {
      setIsTyping(false);
      toast.error("Error fetching question");
    }
  };

  // ===================================
  // STEP 3 — SUBMIT ANSWER
  // ===================================
  const handleSubmitAnswer = async (answerText) => {
    if (!currentQ) return;

    pushMessage({
      id: "u-" + currentQ.question_id,
      type: "user",
      text: answerText,
    });

    try {
      const res = await axios.post("/api/mock-v2/submit-answer", {
        exchange_id: currentQ.question_id,
        user_answer: answerText
      });

      const fb = res.data.feedback;
      pushMessage({
        id: "fb-" + currentQ.question_id,
        type: "feedback",
        text: fb
      });

      // Auto-load next question after feedback
      setTimeout(() => fetchNextQuestion(), 1200);

    } catch (err) {
      toast.error("Failed to submit answer");
    }
  };

  // ===================================
  // STEP 4 — FINAL REPORT
  // ===================================
  const generateReport = async () => {
    setMode("analyzing");
    try {
      await axios.post(`/api/mock-v2/${sessionId}/end`);
      const res = await axios.get(`/api/mock-v2/${sessionId}/results`);
      setReport(res.data);
      setMode("result");
    } catch (err) {
      setMode("result");
      toast.error("Scoring failed");
    }
  };

  // ===================================
  // UI RENDERS
  // ===================================

  // -------------------------------
  // SETUP SCREEN (NEW)
  // -------------------------------
  if (mode === "setup") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-gray-50 to-indigo-100 p-6">
        <div className="bg-white rounded-3xl shadow-xl max-w-4xl w-full grid md:grid-cols-2">
          
          {/* Left Display */}
          <div className="p-10 bg-indigo-600 text-white rounded-l-3xl flex flex-col justify-between">
            <div>
              <h1 className="text-4xl font-bold mb-4">Mock Interview</h1>
              <p className="text-indigo-200 text-lg">
                Practice real interview questions with AI.
              </p>
            </div>

            <ul className="space-y-3 mt-10">
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                Role-specific adaptive questions
              </li>
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                Real-time AI micro-feedback
              </li>
              <li className="flex items-center gap-3">
                <span className="w-3 h-3 bg-white rounded-full"></span>
                Full performance report at the end
              </li>
            </ul>
          </div>

          {/* Form Side */}
          <div className="p-10">
            <h2 className="text-2xl font-bold mb-6">Configure Interview</h2>

            <div className="space-y-6">
              
              {/* Role */}
              <div>
                <label className="font-bold text-gray-700">Target Role</label>
                <input
                  className="mt-2 w-full p-3 border rounded-xl"
                  placeholder="e.g. Frontend Developer"
                  value={sessionConfig.target_role}
                  onChange={(e) => setSessionConfig({ ...sessionConfig, target_role: e.target.value })}
                />
              </div>

              {/* Difficulty */}
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

              {/* Question Count */}
              <div>
                <label className="font-bold text-gray-700">Number of Questions</label>
                <select
                  className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.question_count}
                  onChange={(e) =>
                    setSessionConfig({ ...sessionConfig, question_count: parseInt(e.target.value) })
                  }
                >
                  <option value="3">3 (Quick)</option>
                  <option value="5">5 (Standard)</option>
                  <option value="8">8 (Deep)</option>
                </select>
              </div>

              {/* Resume */}
              <div>
                <label className="font-bold text-gray-700">Use Resume? (Optional)</label>
                <select
                  className="mt-2 w-full p-3 border rounded-xl"
                  value={sessionConfig.resume_id}
                  onChange={(e) =>
                    setSessionConfig({ ...sessionConfig, resume_id: e.target.value })
                  }
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
                className="mt-4 w-full py-4 bg-indigo-600 text-white rounded-xl font-bold text-lg hover:bg-indigo-700"
              >
                Start Interview
              </button>
            </div>
          </div>

        </div>
      </div>
    );
  }

  // -------------------------------
  // INTERVIEW (Chat UI)
  // -------------------------------
  if (mode === "interview") {
    return (
      <div className="min-h-screen flex bg-gray-50">
        
        {/* Sidebar */}
        <SidebarStatus
          currentIndex={currentQ?.current_index}
          total={currentQ?.total_questions}
          difficulty={sessionConfig.difficulty}
          role={sessionConfig.target_role}
        />

        {/* Chat Area */}
        <div className="flex-grow flex flex-col">
          
          {/* Chat timeline */}
          <div className="flex-grow overflow-y-auto p-8 pb-32">
            <ChatTimeline messages={messages} />
            {isTyping && <TypingIndicator />}
          </div>

          {/* Answer bar */}
          <AnswerBar onSubmit={handleSubmitAnswer} />
        </div>
      </div>
    );
  }

  // -------------------------------
  // ANALYZING
  // -------------------------------
  if (mode === "analyzing") {
    return (
      <div className="min-h-screen flex flex-col items-center justify-center text-center bg-gray-50">
        <div className="w-20 h-20 border-4 border-indigo-200 border-t-indigo-600 animate-spin rounded-full"></div>
        <h2 className="text-2xl font-bold mt-6 text-gray-700">
          Generating your interview report…
        </h2>
        <p className="text-gray-500 mt-2">
          Evaluating technical depth, clarity, structure and impact.
        </p>
      </div>
    );
  }

  // -------------------------------
  // RESULTS
  // -------------------------------
  if (mode === "result" && report) {
    // Your existing results dashboard stays intact
    // We reuse your same report UI
    return <YourExistingReportUI report={report} onRestart={() => setMode("setup")} />;
  }

  return null;
}

export default MockPractice;
