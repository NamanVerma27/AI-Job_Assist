// frontend/src/components/mock/MockResult.jsx
import React, { useEffect } from "react";
import { FaCheckCircle, FaExclamationTriangle, FaArrowLeft } from "react-icons/fa";
import { motion } from "framer-motion";
import confetti from "canvas-confetti";
import AdvancedGauge from "../components/AdvancedGauge"; // YOUR ADVANCED GAUGE COMPONENT
import toast from "react-hot-toast";

export default function MockResult({ report, onRestart }) {

  // Celebrate high score
  useEffect(() => {
    if (!report) return;
    if (report.overall_score >= 70) {
      setTimeout(() => {
        confetti({
          particleCount: 120,
          spread: 70,
          origin: { y: 0.6 }
        });
      }, 400);
    }
  }, [report]);

  if (!report) {
    return (
      <div className="p-10 text-center">
        <p>No report available</p>
      </div>
    );
  }

  const dims = report.dimensions || {};
  const feedback = report.feedback || {};
  const transcript = report.transcript || [];

  return (
    <div className="min-h-screen bg-gray-50 p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-10">

        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Interview Results</h1>
            <p className="text-gray-500 text-sm">{report.session_id}</p>
          </div>
          <button
            onClick={onRestart}
            className="flex items-center gap-2 bg-white border border-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-100 transition"
          >
            <FaArrowLeft /> Back to Setup
          </button>
        </div>

        {/* Score + Dimensions */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-8">

          {/* Animated Score */}
          <motion.div
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            className="bg-white p-8 rounded-2xl shadow border flex flex-col items-center justify-center"
          >
            <h3 className="text-gray-400 uppercase text-xs font-bold tracking-wider mb-4">
              Overall Score
            </h3>

            <AdvancedGauge value={report.overall_score} />

            <p className="text-sm text-gray-500 mt-4">Based on clarity, structure, evidence & action</p>
          </motion.div>

          {/* Performance Breakdown */}
          <div className="md:col-span-2 bg-white p-8 rounded-2xl shadow border">
            <h3 className="font-bold text-gray-800 mb-6">Performance Breakdown</h3>

            <div className="space-y-4">
              {Object.entries(dims).map(([key, score]) => (
                <div key={key}>
                  <div className="flex justify-between text-sm font-medium mb-1">
                    <span className="text-gray-600 capitalize">{key.replace("_", " ")}</span>
                    <span className="text-gray-900">{score}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-2.5">
                    <div
                      className="bg-indigo-600 h-2.5 rounded-full transition-all"
                      style={{ width: `${score}%` }}
                    ></div>
                  </div>
                </div>
              ))}
            </div>
          </div>

        </div>

        {/* Strengths + Weaknesses + Quick Wins */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">

          {/* Strengths */}
          <div className="bg-green-50 p-6 rounded-2xl border border-green-100">
            <h3 className="font-bold text-green-800 mb-4 flex items-center gap-2">
              <FaCheckCircle /> Strengths
            </h3>
            <ul className="space-y-2">
              {feedback.strengths?.map((s, i) => (
                <li key={i} className="flex items-start gap-2 text-green-700 text-sm">
                  <span>•</span> {s}
                </li>
              ))}
            </ul>
          </div>

          {/* Weaknesses */}
          <div className="bg-red-50 p-6 rounded-2xl border border-red-100">
            <h3 className="font-bold text-red-800 mb-4 flex items-center gap-2">
              <FaExclamationTriangle /> Weaknesses
            </h3>
            <ul className="space-y-2">
              {feedback.weaknesses?.map((w, i) => (
                <li key={i} className="flex items-start gap-2 text-red-700 text-sm">
                  <span>•</span> {w}
                </li>
              ))}
            </ul>
          </div>

        </div>

        {/* Transcript */}
        <div className="bg-white rounded-2xl shadow border overflow-hidden">
          <div className="p-6 border-b bg-gray-50">
            <h3 className="font-bold text-gray-800 text-lg">
              📝 Detailed Transcript & Improvements
            </h3>
            <p className="text-sm text-gray-500">Compare your answers with AI-rewrites</p>
          </div>

          <div className="divide-y">
            {transcript.map((item, i) => (
              <motion.div
                key={i}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.25 }}
                className="p-6 hover:bg-gray-50 transition"
              >
                <div className="mb-4">
                  <span className="text-xs font-bold text-indigo-500 uppercase tracking-wider">
                    Question {i + 1}
                  </span>
                  <h4 className="text-lg font-medium text-gray-900 mt-1">{item.question}</h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

                  {/* User Answer */}
                  <div className="bg-red-50 p-4 rounded-xl border border-red-100">
                    <h5 className="text-sm font-bold text-red-800 mb-2">
                      <FaExclamationTriangle /> Your Answer
                    </h5>
                    <p className="text-gray-800 text-sm whitespace-pre-wrap">
                      {item.user_answer || "(No answer provided)"}
                    </p>
                    <div className="mt-3 pt-3 border-t border-red-200">
                      <p className="text-xs text-red-700 italic">{item.feedback}</p>
                    </div>
                  </div>

                  {/* Improved Answer */}
                  <div className="bg-green-50 p-4 rounded-xl border border-green-100">
                    <h5 className="text-sm font-bold text-green-800 mb-2 flex items-center gap-2">
                      <FaCheckCircle /> AI Suggested Answer
                    </h5>
                    <p className="text-gray-900 text-sm whitespace-pre-wrap">
                      {item.improved_answer}
                    </p>
                    <div className="mt-2 text-right">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(item.improved_answer);
                          toast.success("Copied!");
                        }}
                        className="text-xs text-green-700 font-bold hover:underline"
                      >
                        Copy
                      </button>
                    </div>
                  </div>

                </div>
              </motion.div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
