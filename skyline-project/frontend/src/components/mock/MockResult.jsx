// frontend/src/components/mock/MockResult.jsx

import React from "react";
import { motion } from "framer-motion";
import { FaCheckCircle, FaExclamationTriangle, FaCopy } from "react-icons/fa";
import toast from "react-hot-toast";

export default function MockResult({ report, onRestart }) {
  if (!report) return null;

  const score = report.overall_score || 0;
  const transcript = report.transcript || [];
  const role = report.role || "Interview";

  // Gauge stroke calculation
  const circumference = 2 * Math.PI * 60;
  const strokeDashoffset = circumference - (score / 100) * circumference;

  return (
    <div className="min-h-screen bg-gray-50 p-6 md:p-10">
      <div className="max-w-6xl mx-auto space-y-10">
        {/* Header */}
        <div className="flex justify-between items-center">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Interview Results</h1>
            <p className="text-gray-600">Role: {role}</p>
          </div>

          <button
            onClick={onRestart}
            className="bg-white border border-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-100"
          >
            Back to Mock Practice
          </button>
        </div>

        {/* Overall Score Gauge */}
        <motion.div
          initial={{ opacity: 0, scale: 0.92 }}
          animate={{ opacity: 1, scale: 1 }}
          className="bg-white p-10 rounded-3xl shadow-sm border flex flex-col items-center"
        >
          <h2 className="text-gray-500 text-sm font-semibold uppercase tracking-wide">
            Overall Performance
          </h2>

          <div className="relative w-48 h-48 my-6">
            <svg className="w-full h-full transform -rotate-90">
              <circle
                cx="60"
                cy="60"
                r="60"
                stroke="#E5E7EB"
                strokeWidth="12"
                fill="none"
              />
              <motion.circle
                cx="60"
                cy="60"
                r="60"
                stroke="#6366F1"
                strokeWidth="12"
                fill="none"
                strokeDasharray={circumference}
                strokeDashoffset={circumference}
                animate={{ strokeDashoffset }}
                transition={{ duration: 1.2, ease: "easeInOut" }}
                strokeLinecap="round"
              />
            </svg>

            <div className="absolute inset-0 flex items-center justify-center">
              <span className="text-4xl font-bold text-indigo-600">{score}</span>
            </div>
          </div>

          {/* Small celebratory animation for > 70 */}
          {score >= 70 && (
            <motion.div
              className="text-green-600 font-medium mt-2"
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
            >
              🎉 Great Job! Strong performance.
            </motion.div>
          )}
        </motion.div>

        {/* Strengths + Weaknesses */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Strengths */}
          <div className="bg-green-50 p-6 rounded-2xl border border-green-100">
            <h3 className="font-bold text-green-800 mb-4 flex items-center gap-2">
              <FaCheckCircle /> Strengths
            </h3>

            <ul className="space-y-2">
              {report.history?.flatMap(h => h.evaluation.strengths || []).length > 0
                ? report.history.flatMap((h, i) =>
                    (h.evaluation.strengths || []).map((s, idx) => (
                      <li
                        key={`${i}-${idx}`}
                        className="flex items-start text-green-700 text-sm gap-2"
                      >
                        <span className="mt-1">•</span> {s}
                      </li>
                    ))
                  )
                : <p className="text-green-700 text-sm">No strengths detected</p>}
            </ul>
          </div>

          {/* Weaknesses */}
          <div className="bg-red-50 p-6 rounded-2xl border border-red-100">
            <h3 className="font-bold text-red-800 mb-4 flex items-center gap-2">
              <FaExclamationTriangle /> Areas to Improve
            </h3>

            <ul className="space-y-2">
              {report.history?.flatMap(h => h.evaluation.weaknesses || []).length > 0
                ? report.history.flatMap((h, i) =>
                    (h.evaluation.weaknesses || []).map((w, idx) => (
                      <li
                        key={`${i}-${idx}`}
                        className="flex items-start text-red-700 text-sm gap-2"
                      >
                        <span className="mt-1">•</span> {w}
                      </li>
                    ))
                  )
                : <p className="text-red-700 text-sm">No major weaknesses.</p>}
            </ul>
          </div>
        </div>

        {/* Transcript */}
        <div className="bg-white rounded-3xl shadow-sm border overflow-hidden">
          <div className="p-6 border-b bg-gray-50">
            <h3 className="font-bold text-gray-800 text-lg">📝 Detailed Transcript</h3>
            <p className="text-sm text-gray-500">
              Review your answers with suggested improvements.
            </p>
          </div>

          <div className="divide-y">
            {transcript.map((item, idx) => (
              <div key={idx} className="p-6 hover:bg-gray-50 transition">
                <div className="mb-4">
                  <span className="text-xs font-bold text-indigo-500 uppercase">
                    Question {idx + 1}
                  </span>
                  <h4 className="text-lg font-medium text-gray-900 mt-1">
                    {item.question}
                  </h4>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                  {/* User Answer */}
                  <div className="bg-red-50 p-4 rounded-xl border border-red-100">
                    <h5 className="text-sm font-bold text-red-800 mb-2 flex items-center gap-2">
                      <FaExclamationTriangle /> Your Answer
                    </h5>
                    <p className="text-gray-700 text-sm whitespace-pre-wrap">
                      {item.answer || "(No answer provided)"}
                    </p>
                    <div className="mt-3 pt-3 border-t border-red-200">
                      <p className="text-xs text-red-700 italic">
                        Feedback: {item.feedback}
                      </p>
                    </div>
                  </div>

                  {/* Improved Answer */}
                  <div className="bg-green-50 p-4 rounded-xl border border-green-100">
                    <h5 className="text-sm font-bold text-green-800 mb-2 flex items-center gap-2">
                      <FaCheckCircle /> Improved Answer
                    </h5>

                    <p className="text-gray-800 text-sm whitespace-pre-wrap">
                      {item.improvement}
                    </p>

                    <div className="mt-3 text-right">
                      <button
                        onClick={() => {
                          navigator.clipboard.writeText(item.improvement);
                          toast.success("Copied!");
                        }}
                        className="text-xs text-green-700 font-bold hover:underline flex items-center gap-1"
                      >
                        <FaCopy size={12} /> Copy
                      </button>
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

      </div>
    </div>
  );
}
