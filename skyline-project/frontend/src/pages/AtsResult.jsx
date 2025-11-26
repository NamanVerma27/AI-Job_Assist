import React, { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { FaArrowLeft, FaCopy, FaDownload, FaMagic, FaChevronDown, FaChevronUp } from "react-icons/fa";
import Gauge from "../components/Gauge";
import { toast } from "react-hot-toast";
import axios from "axios";

/**
 * ATS Result page with per-quick-win collapse + AI before/after rewrite
 *
 * - Click a quick-win to expand
 * - Use "Rewrite (AI)" to request an LLM rewrite for that specific item
 * - Tries canonical endpoint /api/ai/enhance-ats then legacy /ai/enhance-ats
 * - Defensive parsing for varied response shapes
 */

export default function AtsResult() {
  const navigate = useNavigate();
  const location = useLocation();
  const [report, setReport] = useState(null);

  // Per-item UI state:
  // expanded: { idx: boolean }, rewrites: { idx: { loading, before, after, error } }
  const [expanded, setExpanded] = useState({});
  const [rewrites, setRewrites] = useState({});
  const [enhancingAll, setEnhancingAll] = useState(false);

  useEffect(() => {
    const fromState = location.state?.report;
    if (fromState) {
      setReport(fromState);
      return;
    }

    try {
      const saved = sessionStorage.getItem("ats_report");
      if (saved) setReport(JSON.parse(saved));
    } catch (e) {
      console.warn("Could not load report from sessionStorage:", e);
    }
  }, [location.state]);

  if (!report) {
    return (
      <div className="min-h-screen flex items-center justify-center text-gray-700 text-lg">
        No report data found. Please run an ATS check first.
      </div>
    );
  }

  const breakdown = report.breakdown || {};
  const totalScore = report.total_score ?? 0;

  const getMetricScore = (key) => {
    const val = breakdown[key];
    if (!val) return 0;
    return val.score ?? val.readability_score ?? val.structure_score ?? val.semantic_score ?? val.tone_score ?? 0;
  };

  // Quick wins source (prefer enhancedSuggestions previously stored in report, else insights.quick_wins or gap_analysis)
  const rawQuickWins = report.insights?.quick_wins ?? report.insights?.gap_analysis ?? [];
  // Normalize to array of strings or objects
  const quickWins = Array.isArray(rawQuickWins) ? rawQuickWins : [];

  // Toggle expand
  const toggleExpand = (idx) => {
    setExpanded((s) => ({ ...s, [idx]: !s[idx] }));
  };

  // Per-item rewrite using LLM: sends { report, quick_win: item } to backend
  const rewriteQuickWin = async (idx) => {
    const item = quickWins[idx];
    if (!item) {
      toast.error("Item not found.");
      return;
    }

    // If already have after text, toggle expand and return
    if (rewrites[idx]?.after) {
      setExpanded((s) => ({ ...s, [idx]: true }));
      return;
    }

    // Set loading
    setRewrites((s) => ({ ...s, [idx]: { ...(s[idx] || {}), loading: true, error: null } }));

    const payload = { report, quick_win: item };

    // try canonical then legacy endpoint
    const endpoints = ["/api/ai/enhance-ats", "/ai/enhance-ats"];
    let resp = null;
    let lastErr = null;
    try {
      for (const ep of endpoints) {
        try {
          resp = await axios.post(ep, payload, { timeout: 30000 });
          if (resp && resp.status >= 200 && resp.status < 300) break;
        } catch (e) {
          lastErr = e;
        }
      }

      if (!resp) throw lastErr ?? new Error("No response from AI endpoint.");

      console.debug("Per-item AI raw response:", resp.data);

      // Defensive extraction: prefer array of enhancements or object with before->after
      // Candidates: resp.data.data.enhanced, resp.data.enhanced, resp.data.data, resp.data
      const candidate =
        resp.data?.data?.enhanced ??
        resp.data?.enhanced ??
        resp.data?.data ??
        resp.data ??
        null;

      // Try to pull single suggestion for this quick_win
      // Common patterns:
      // - [{ before: "...", after: "..." }, ...]
      // - { enhanced: [{...}] }
      // - { result: [{before, after}] }
      let beforeText = typeof item === "string" ? item : item?.recommendation ?? item?.title ?? JSON.stringify(item);
      let afterText = null;

      if (Array.isArray(candidate) && candidate.length > 0) {
        // If array of objects, try to find matching by text or take first
        const found = candidate.find((c) => {
          if (!c) return false;
          if (typeof c === "string") return c.includes(String(beforeText).slice(0, 20));
          const txt = c.before ?? c.input ?? c.source ?? c.original ?? "";
          return typeof txt === "string" && txt.includes(String(beforeText).slice(0, 12));
        });
        const chosen = found || candidate[0];
        afterText = chosen?.after ?? chosen?.rewrite ?? chosen?.enhanced ?? (typeof chosen === "string" ? chosen : null);
      } else if (candidate && typeof candidate === "object") {
        // candidate may be object containing 'after' or 'rewrite'
        afterText = candidate.after ?? candidate.rewrite ?? candidate.enhanced ?? null;
        if (!afterText && Array.isArray(candidate.enhancements) && candidate.enhancements.length > 0) {
          const c0 = candidate.enhancements[0];
          afterText = c0.after ?? c0.rewrite ?? (typeof c0 === "string" ? c0 : null);
        }
      }

      // Fallback: if server returned text in resp.data.text or resp.data.output
      if (!afterText) {
        afterText = resp.data?.text ?? resp.data?.output ?? null;
      }

      // Final fallback: simple transformation if nothing else: prefix suggested rewrite
      if (!afterText) {
        afterText = `Rewrite suggestion (AI returned unexpected shape). Original: ${String(beforeText).slice(0, 200)}`;
        toast("AI responded but output couldn't be parsed exactly — showing fallback.", { icon: "⚠️" });
      } else {
        toast.success("Rewrite generated by AI");
      }

      setRewrites((s) => ({ ...s, [idx]: { ...(s[idx] || {}), before: beforeText, after: afterText, loading: false, error: null } }));
      setExpanded((s) => ({ ...s, [idx]: true }));
    } catch (err) {
      console.error("Per-item rewrite error:", err);
      setRewrites((s) => ({ ...s, [idx]: { ...(s[idx] || {}), loading: false, error: "AI rewrite failed." } }));
      toast.error("AI rewrite failed. Check console for details.");
    }
  };

  // Export function reused
  const exportEnhanced = (data) => {
    try {
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "quick_wins.json";
      a.click();
      URL.revokeObjectURL(url);
      toast.success("Exported quick wins");
    } catch (err) {
      toast.error("Export failed.");
    }
  };

  // MiniBar component
  const MiniBar = ({ value = 0, colorClass = "bg-gradient-to-r from-indigo-500 to-blue-500" }) => {
    const clamped = Math.max(0, Math.min(100, Math.round(value)));
    return (
      <div className="mt-4 w-full bg-white/60 rounded-full h-2.5 overflow-hidden border border-white/20">
        <div
          className={`h-2.5 ${colorClass} rounded-full transition-all duration-600`}
          style={{ width: `${clamped}%`, boxShadow: "0 6px 18px rgba(59,130,246,0.12)" }}
        />
      </div>
    );
  };

  const cardClass = "backdrop-blur-xl bg-white/40 shadow-xl border border-white/30 rounded-3xl p-6";

  // quickWinsToShow prefers any enhancedSuggestions that might exist on the report (we keep compatibility)
  const quickWinsToShow = report.enhanced_quick_wins ?? report.insights?.quick_wins ?? report.insights?.gap_analysis ?? [];

  return (
    <div className="min-h-screen bg-gradient-to-br from-[#EEF3FF] to-[#F9FAFF] py-10 px-6">
      <div className="max-w-6xl mx-auto space-y-10">
        <button onClick={() => navigate("/ats")} className="inline-flex items-center gap-2 text-gray-600 hover:text-indigo-600">
          <FaArrowLeft /> Back to ATS Checker
        </button>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          <div className={`${cardClass} flex flex-col items-center justify-center pb-10`}>
            <h2 className="text-xl font-bold text-gray-900 mb-4">Overall ATS Score</h2>
            <Gauge value={totalScore} animate />
            <div className="mt-4 text-sm text-gray-600 text-center">Combined: Keywords, Structure, Semantics, Readability, Tone</div>
          </div>

          <div className={`${cardClass} col-span-1 lg:col-span-2`}>
            <h2 className="text-xl font-bold text-gray-900">Role Detection</h2>
            <p className="mt-2">
              <span className="font-semibold text-indigo-700">{report.role?.role ?? "general"}</span>{" "}
              ({Math.round((report.role?.confidence ?? 0) * 100)}% confidence)
            </p>
            <p className="mt-4 text-gray-600 leading-relaxed">{report.insights?.overall_summary}</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-6">
          {[
            ["structure", "Structural Quality", "Sections & formatting", "from-indigo-400 to-indigo-600"],
            ["keywords", "Keyword Match", "JD alignment", "from-indigo-400 to-blue-500"],
            ["semantics", "Semantic Relevance", "Contextual similarity", "from-violet-400 to-indigo-500"],
            ["readability", "Readability", "Clarity & concision", "from-cyan-400 to-blue-400"],
            ["tone", "Tone & Impact", "Action words & achievements", "from-green-400 to-indigo-400"],
          ].map(([key, title, desc, color]) => {
            const score = getMetricScore(key) ?? 0;
            return (
              <div key={key} className={`${cardClass} flex flex-col justify-between`}>
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">{title}</h3>
                  <p className="text-sm text-gray-500 mt-1">{desc}</p>
                </div>

                <div className="mt-4 flex items-center justify-between">
                  <div className="text-3xl font-bold text-indigo-600">{score}</div>
                  <div style={{ minWidth: 120, marginLeft: 16, flex: 1 }}>
                    <MiniBar value={score} colorClass={`bg-gradient-to-r ${color}`} />
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Quick Wins with per-item collapse & rewrite */}
        <div className={cardClass}>
          <div className="flex items-center justify-between mb-4">
            <div>
              <h2 className="text-xl font-bold text-gray-900">Quick Wins</h2>
              <div className="text-xs text-gray-400">High-impact, low-effort improvements</div>
            </div>

            <div className="flex items-center gap-3">
              <button
                onClick={async () => {
                  // Enhance all: call /api/ai/enhance-ats for whole report (keep existing behavior)
                  setEnhancingAll(true);
                  try {
                    const endpoints = ["/api/ai/enhance-ats", "/ai/enhance-ats"];
                    let resp = null;
                    for (const ep of endpoints) {
                      try {
                        resp = await axios.post(ep, { report }, { timeout: 30000 });
                        if (resp && resp.status >= 200 && resp.status < 300) break;
                      } catch (e) {
                        // try next
                      }
                    }
                    if (!resp) throw new Error("No AI response");
                    const candidate = resp.data?.data?.enhanced ?? resp.data?.enhanced ?? resp.data?.data ?? resp.data ?? null;
                    // if candidate is array, set enhanced_quick_wins to it on the report copy
                    if (Array.isArray(candidate)) {
                      setRewrites((s) => s); // noop (keep per-item rewrites)
                      // attach enhanced to report (not persisted server-side, only UI)
                      setReport((r) => ({ ...r, enhanced_quick_wins: candidate }));
                      toast.success("Enhanced quick wins applied");
                    } else {
                      toast.success("AI responded (unexpected shape) — check console.");
                      console.debug("AI enhance (all) response:", resp.data);
                    }
                  } catch (err) {
                    console.error("Enhance all failed:", err);
                    toast.error("AI enhancement failed for all items.");
                  } finally {
                    setEnhancingAll(false);
                  }
                }}
                disabled={enhancingAll}
                className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-600 text-white text-sm hover:bg-indigo-700 transition"
                title="Enhance all quick wins using AI"
              >
                <FaMagic /> Enhance (AI)
              </button>

              <button
                onClick={() => {
                  const source = report.enhanced_quick_wins ?? quickWins;
                  if (!source || source.length === 0) {
                    toast.error("No quick wins to copy.");
                    return;
                  }
                  navigator.clipboard.writeText(JSON.stringify(source, null, 2));
                  toast.success("Copied quick wins JSON");
                }}
                className="px-3 py-1 rounded-full bg-white border border-gray-200 text-xs inline-flex items-center gap-2 hover:bg-gray-50 transition"
                title="Copy quick wins JSON"
              >
                <FaCopy /> Copy
              </button>

              <button
                onClick={() => {
                  const source = report.enhanced_quick_wins ?? quickWins;
                  if (!source || source.length === 0) {
                    toast.error("No quick wins to export.");
                    return;
                  }
                  exportEnhanced(source);
                }}
                className="px-3 py-1 rounded-full bg-white border border-gray-200 text-xs inline-flex items-center gap-2 hover:bg-gray-50 transition"
                title="Export quick wins JSON"
              >
                <FaDownload /> Export
              </button>
            </div>
          </div>

          <ul className="space-y-3">
            {quickWinsToShow && quickWinsToShow.length > 0 ? (
              quickWinsToShow.map((item, idx) => {
                const r = rewrites[idx] || {};
                const isExpanded = !!expanded[idx];
                const beforeText = r.before ?? (typeof item === "string" ? item : item?.recommendation ?? item?.title ?? JSON.stringify(item));
                const afterText = r.after ?? (report.enhanced_quick_wins && Array.isArray(report.enhanced_quick_wins[idx]) ? report.enhanced_quick_wins[idx] : null);

                return (
                  <li key={idx} className="rounded-xl bg-white/60 backdrop-blur border border-gray-100 shadow overflow-hidden">
                    <div className="px-4 py-3 flex items-center justify-between gap-4">
                      <div className="flex-1 text-gray-800">
                        <div className="font-semibold">{typeof item === "string" ? item : item?.title ?? (item.recommendation ?? "").slice(0, 140)}</div>
                        <div className="text-xs text-gray-500 mt-1">{item?.category ?? ""}</div>
                      </div>

                      <div className="flex items-center gap-2">
                        <button
                          onClick={() => rewriteQuickWin(idx)}
                          disabled={r.loading || !!afterText}
                          className={`px-3 py-1 rounded-full text-xs inline-flex items-center gap-2 ${
                            r.loading ? "bg-gray-200 text-gray-600" : afterText ? "bg-green-50 text-green-700 border border-green-100" : "bg-white border border-gray-200 hover:bg-gray-50"
                          }`}
                          title={afterText ? "Rewrite available" : "Rewrite this suggestion using AI"}
                        >
                          {r.loading ? "Thinking..." : afterText ? "Rewritten" : "Rewrite (AI)"}
                        </button>

                        <button
                          onClick={() => toggleExpand(idx)}
                          className="p-2 rounded-full bg-white border border-gray-100 hover:bg-gray-50"
                          aria-expanded={isExpanded}
                          aria-controls={`quickwin-${idx}`}
                          title={isExpanded ? "Collapse" : "Expand"}
                        >
                          {isExpanded ? <FaChevronUp /> : <FaChevronDown />}
                        </button>
                      </div>
                    </div>

                    {/* Expandable content (fixed: no peek-through when collapsed) */}
                    <div
                      id={`quickwin-${idx}`}
                      aria-hidden={!isExpanded}
                      className={`transition-all duration-300 ease-in-out overflow-hidden ${
                        isExpanded
                          ? "max-h-96 p-4 opacity-100"   // expanded: allow content, apply padding
                          : "max-h-0 p-0 opacity-0"       // collapsed: remove padding so nothing peeks, fade out
                      }`}
                      style={{ willChange: "max-height, opacity, padding" }}
                    >
                      <div className="text-sm text-gray-700">
                        <div className="mb-3">
                          <div className="text-xs text-gray-500 mb-1">Before</div>
                          <div className="p-3 rounded-lg bg-white border border-gray-100 text-sm">{beforeText}</div>
                        </div>

                        <div>
                          <div className="text-xs text-gray-500 mb-1">After (AI rewrite)</div>
                          {r.loading ? (
                            <div className="p-3 rounded-lg bg-white border border-gray-100 text-sm text-gray-500">Generating rewrite...</div>
                          ) : r.error ? (
                            <div className="p-3 rounded-lg bg-red-50 border border-red-100 text-sm text-red-700">{r.error}</div>
                          ) : afterText ? (
                            <div className="p-3 rounded-lg bg-white border border-gray-100 text-sm text-gray-800">{afterText}</div>
                          ) : (
                            <div className="p-3 rounded-lg bg-white border border-dashed border-gray-200 text-sm text-gray-500">
                              No rewrite yet. Click <strong>Rewrite (AI)</strong> to generate a polished version.
                            </div>
                          )}
                        </div>
                      </div>
                    </div>
                  </li>
                );
              })
            ) : (
              <li className="p-4 rounded-xl bg-white/60 backdrop-blur border border-gray-100 shadow text-gray-600">No quick wins found.</li>
            )}
          </ul>
        </div>

        <div className="text-center text-xs text-gray-500 mt-10">Structure · Keywords · Semantic Match · Readability · Tone</div>
      </div>
    </div>
  );
}
