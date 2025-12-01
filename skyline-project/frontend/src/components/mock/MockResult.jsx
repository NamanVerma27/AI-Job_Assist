// src/components/mock/MockResult.jsx
import React, { useEffect, useRef, useState } from "react";
import PropTypes from "prop-types";
import { FaClipboard, FaRedo } from "react-icons/fa";
import "./mock_result.css";

/**
 * MockResult
 * Props:
 *  - report: {
 *      overall_score: number (0-100) | null,
 *      dimensions: { clarity: 80, impact: 60, ... },
 *      feedback: { quick_wins: [], strengths: [], weaknesses: [] },
 *      transcript: [{ question, user_answer, improved_answer, feedback }]
 *    }
 *  - onRestart(): callback to restart a session
 */
export default function MockResult({ report = {}, onRestart = () => {} }) {
  const score = report.overall_score ?? null;
  const celebrate = score !== null && score >= 75;
  const confettiRef = useRef(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (celebrate) {
      // trigger CSS confetti burst by adding a class briefly
      const el = confettiRef.current;
      if (!el) return;
      el.classList.remove("confetti-burst");
      // allow reflow
      // eslint-disable-next-line no-unused-expressions
      el.offsetWidth;
      el.classList.add("confetti-burst");
    }
  }, [celebrate, score]);

  const copySummary = async () => {
    const text = generateSummary(report);
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      setCopied(false);
    }
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      <div className="bg-white rounded-2xl shadow-sm p-6 grid md:grid-cols-3 gap-6 items-center">
        {/* SCORE CARD */}
        <div className="flex flex-col items-center justify-center gap-4">
          <div className="relative">
            <svg className="w-40 h-40" viewBox="0 0 120 120" aria-hidden>
              <defs>
                <linearGradient id="grad" x1="0" x2="1">
                  <stop offset="0%" stopColor="#4F46E5" />
                  <stop offset="100%" stopColor="#06b6d4" />
                </linearGradient>
              </defs>
              <circle cx="60" cy="60" r="48" stroke="#EEF2FF" strokeWidth="18" fill="none" />
              <circle
                cx="60"
                cy="60"
                r="48"
                stroke="url(#grad)"
                strokeWidth="18"
                strokeLinecap="round"
                fill="none"
                strokeDasharray={`${score ?? 0} ${100 - (score ?? 0)}`}
                transform="rotate(-90 60 60)"
              />
            </svg>

            <div className="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
              <div className={`text-4xl font-extrabold ${score >= 60 ? "text-indigo-900" : "text-gray-800"}`}>
                {score === null ? "—" : `${score}`}
              </div>
              <div className="text-sm text-gray-500 mt-1">Overall Score</div>
            </div>

            {/* confetti container */}
            <div ref={confettiRef} className="confetti-container pointer-events-none" aria-hidden />
          </div>

          <div className="flex gap-2">
            <button
              onClick={copySummary}
              className="bg-indigo-600 text-white px-4 py-2 rounded-md flex items-center gap-2 hover:bg-indigo-700"
              aria-label="Copy summary"
            >
              <FaClipboard /> <span className="hidden sm:inline">{copied ? "Copied" : "Copy summary"}</span>
            </button>

            <button
              onClick={onRestart}
              className="bg-white border border-gray-200 px-4 py-2 rounded-md flex items-center gap-2 hover:bg-gray-50"
            >
              <FaRedo /> Restart
            </button>
          </div>
        </div>

        {/* PERFORMANCE BREAKDOWN */}
        <div className="md:col-span-2">
          <h3 className="text-lg font-semibold text-gray-800 mb-4">Performance breakdown</h3>
          <div className="grid md:grid-cols-2 gap-4">
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="text-sm font-medium text-gray-600 mb-3">Key dimensions</h4>
              <div className="space-y-3">
                {report.dimensions && Object.keys(report.dimensions).length > 0 ? (
                  Object.entries(report.dimensions).map(([k, v]) => (
                    <div key={k}>
                      <div className="flex justify-between text-xs font-medium text-gray-700 mb-1">
                        <span className="capitalize">{k.replace(/_/g, " ")}</span>
                        <span>{v}%</span>
                      </div>
                      <div className="w-full bg-white rounded-full h-2.5">
                        <div className="bg-indigo-600 h-2.5 rounded-full" style={{ width: `${v}%` }} />
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-gray-500">No dimension data available.</div>
                )}
              </div>
            </div>

            <div className="bg-white p-4 rounded-lg border">
              <h4 className="text-sm font-medium text-gray-600 mb-3">Quick wins</h4>
              {report.feedback && report.feedback.quick_wins && report.feedback.quick_wins.length > 0 ? (
                <ul className="space-y-2">
                  {report.feedback.quick_wins.map((w, i) => (
                    <li key={i} className="text-sm bg-indigo-50 p-2 rounded-md">
                      <strong className="text-indigo-800">{w.title || "Tip"}</strong>
                      <div className="text-xs text-indigo-700">{w.description || w}</div>
                    </li>
                  ))}
                </ul>
              ) : (
                <div className="text-sm text-gray-500">No quick wins found.</div>
              )}
            </div>
          </div>

          {/* Transcript */}
          <div className="mt-6 bg-white border rounded-lg p-4">
            <h4 className="font-semibold text-gray-700 mb-3">Detailed transcript & improvements</h4>
            <div className="divide-y">
              {report.transcript && report.transcript.length > 0 ? (
                report.transcript.map((t, i) => (
                  <div className="py-4" key={i}>
                    <div className="text-xs text-gray-500">Question {i + 1}</div>
                    <div className="text-sm font-medium text-gray-900 mt-1 mb-2">{t.question}</div>

                    <div className="grid md:grid-cols-2 gap-4">
                      <div className="bg-red-50 p-3 rounded-md border border-red-100">
                        <div className="text-xs font-bold text-red-700 mb-2">Your answer</div>
                        <div className="text-sm text-gray-800 whitespace-pre-wrap">{t.user_answer || "(No answer)"}</div>
                        <div className="text-xs text-red-600 mt-2 italics">Feedback: {t.feedback || "—"}</div>
                      </div>

                      <div className="bg-green-50 p-3 rounded-md border border-green-100">
                        <div className="text-xs font-bold text-green-800 mb-2">AI suggested</div>
                        <div className="text-sm text-gray-800 whitespace-pre-wrap">{t.improved_answer || "(No suggestion)"}</div>
                        <div className="text-right mt-3">
                          <button
                            onClick={() => {
                              navigator.clipboard.writeText(t.improved_answer || "");
                              // small UX: flash
                              setCopied(true);
                              setTimeout(() => setCopied(false), 1400);
                            }}
                            className="text-xs font-medium text-green-700 hover:underline"
                          >
                            Copy suggestion
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="p-4 text-sm text-gray-500">Transcript not available.</div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

MockResult.propTypes = {
  report: PropTypes.object,
  onRestart: PropTypes.func
};

/* Helper: generate a short plain-text summary for clipboard */
function generateSummary(report = {}) {
  const score = report.overall_score ?? "N/A";
  const dims = report.dimensions ? Object.entries(report.dimensions).map(([k, v]) => `${k}:${v}%`).join(", ") : "";
  const strengths = report.feedback?.strengths?.slice(0, 3).join("; ") || "";
  const quick = report.feedback?.quick_wins?.slice(0, 3).map(q => (q.title ? `${q.title} — ${q.description || ""}` : q)).join("; ") || "";
  return `Score: ${score}\nDimensions: ${dims}\nStrengths: ${strengths}\nQuickWins: ${quick}`;
}
