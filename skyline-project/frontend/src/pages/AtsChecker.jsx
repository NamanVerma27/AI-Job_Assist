// frontend/src/pages/AtsChecker.jsx
import React, { useEffect, useRef, useState } from "react";
import axios from "axios";
import { FaFileAlt, FaSpinner, FaArrowRight, FaUpload } from "react-icons/fa";
import { useNavigate } from "react-router-dom";
import Gauge from "../components/Gauge";

/**
 * Refined ATS Checker (network fallbacks + better UX)
 */

export default function AtsChecker() {
  const navigate = useNavigate();
  const [resumeText, setResumeText] = useState("");
  const [jdText, setJdText] = useState("");
  const [savedResumes, setSavedResumes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);

  // Try to load saved resumes (supports /api/ prefix or not)
  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const tryUrls = ["/api/profile/resumes", "/profile/resumes"];
        let payload = null;
        for (const url of tryUrls) {
          try {
            const res = await axios.get(url);
            const data = res.data?.data ?? res.data;
            if (Array.isArray(data)) {
              payload = data;
              break;
            }
          } catch (e) {
            // try next
          }
        }
        if (mounted && payload) setSavedResumes(payload);
      } catch (e) {
        console.debug("Saved resumes not available:", e?.message || e);
      }
    })();
    return () => (mounted = false);
  }, []);

  const validateInputs = () => {
    if (!resumeText || !resumeText.trim()) {
      setError("Please paste or upload a resume first.");
      return false;
    }
    if (!jdText || !jdText.trim()) {
      setError("Please paste the Job Description to compare.");
      return false;
    }
    setError("");
    return true;
  };

  // POST to ATS endpoint with fallback logic (v2 -> v1)
  const postAtsWithFallback = async (rText, jText) => {
    const payload = { resume_text: rText, jd_text: jText };
    const endpoints = ["/api/resume/ats-score-v2", "/api/resume/ats-score", "/resume/ats-score-v2", "/resume/ats-score"];
    let lastErr = null;
    for (const ep of endpoints) {
      try {
        const resp = await axios.post(ep, payload);
        return resp.data?.data ?? resp.data;
      } catch (err) {
        lastErr = err;
        // continue trying other endpoints
      }
    }
    throw lastErr ?? new Error("No ATS endpoint reachable.");
  };

  // run analysis and navigate to results
  const runAnalysisAndNavigate = async (rText, jText) => {
    setLoading(true);
    setError("");
    try {
      const payload = await postAtsWithFallback(rText, jText);
      try {
        sessionStorage.setItem("ats_report", JSON.stringify(payload));
      } catch (e) {
        console.warn("Could not save report to sessionStorage:", e);
      }
      navigate("/ats-result", { state: { report: payload } });
    } catch (err) {
      console.error("ATS analysis failed:", err);
      const msg = err?.response?.data?.detail || err?.message || "Analysis failed. Check backend or endpoint.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  const handleAnalyzeClick = async () => {
    if (!validateInputs()) return;
    await runAnalysisAndNavigate(resumeText, jdText);
  };

  // Upload file with same fallback logic for endpoints
  const uploadWithFallback = async (file) => {
    const form = new FormData();
    form.append("file", file);
    const endpoints = ["/api/resume/upload-resume", "/resume/upload-resume"];
    let lastErr = null;
    for (const ep of endpoints) {
      try {
        const res = await axios.post(ep, form, { headers: { "Content-Type": "multipart/form-data" } });
        return res.data?.data ?? res.data;
      } catch (err) {
        lastErr = err;
      }
    }
    throw lastErr ?? new Error("No upload endpoint reachable.");
  };

  const handleUploadFile = async (file) => {
    if (!file) return;
    setUploading(true);
    setError("");
    try {
      const payload = await uploadWithFallback(file);
      const content = payload?.content ?? "";
      if (!content || !content.trim()) {
        setError("Uploaded file parsed no text. Try a different file or paste manually.");
      } else {
        setResumeText(content);
        setPreviewOpen(true);
      }
    } catch (err) {
      console.error("Upload failed:", err);
      setError(err?.response?.data?.detail || err?.message || "Upload failed.");
    } finally {
      setUploading(false);
    }
  };

  const onUploadButtonClick = () => fileInputRef.current?.click();

  const handleSelectSaved = (ev) => {
    const id = ev.target.value;
    if (!id) {
      setResumeText("");
      return;
    }
    const selected = savedResumes.find((r) => String(r.id) === String(id));
    if (selected?.content) {
      setResumeText(selected.content);
      setPreviewOpen(true);
    } else {
      alert("Selected saved resume has no parsed text available on the server.");
    }
  };

  // Dev sample loader: try /api/dev/sample-resume then /dev/sample-resume
  const SAMPLE_PATH = "/mnt/data/web-developer-resume-example.pdf";
  const handleLoadSampleAndAutoRun = async () => {
    setLoading(true);
    setError("");
    try {
      const tryUrls = ["/api/dev/sample-resume", "/dev/sample-resume", "/api/dev/sample", "/dev/sample"];
      let content = null;
      for (const u of tryUrls) {
        try {
          const res = await axios.get(u, { params: { path: SAMPLE_PATH } });
          const c = res.data?.data?.content ?? res.data?.content ?? res.data;
          if (c && c.toString().trim()) {
            content = c;
            break;
          }
        } catch (e) {
          // try next
        }
      }
      if (!content) {
        setError("Sample resume could not be loaded. Ensure dev route is available.");
        setLoading(false);
        return;
      }
      setResumeText(content);
      if (jdText && jdText.trim()) {
        await runAnalysisAndNavigate(content, jdText);
      } else {
        setPreviewOpen(true);
        setTimeout(() => {
          const el = document.querySelector("#jd-input");
          if (el) el.focus();
        }, 80);
      }
    } catch (err) {
      console.error("Sample loader failed:", err);
      setError(err?.response?.data?.detail || "Could not load sample. Ensure dev route is enabled.");
    } finally {
      setLoading(false);
    }
  };

  const resumeCharCount = resumeText ? resumeText.length : 0;
  const jdWordCount = jdText ? jdText.trim().split(/\s+/).length : 0;

  return (
    <div className="min-h-screen bg-gradient-to-b from-gray-50 to-white py-12 px-6">
      <div className="max-w-6xl mx-auto">
        {/* Header */}
        <div className="mb-6 flex items-start justify-between gap-6">
          <div>
            <h1 className="text-3xl font-extrabold text-gray-900">ATS Score Checker</h1>
            <p className="text-gray-600 mt-1 max-w-2xl">
              Compare your resume against a job description. Results open in a dedicated dashboard with prioritized fixes.
            </p>
          </div>

          <div className="hidden sm:flex items-center gap-3">
            <button
              onClick={handleLoadSampleAndAutoRun}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-100"
              title="Load developer sample and auto-run (dev)"
              disabled={loading}
            >
              Load sample
            </button>

            <button
              onClick={onUploadButtonClick}
              className="inline-flex items-center gap-2 px-3 py-2 rounded-full bg-white border border-gray-200 text-sm shadow-sm hover:shadow-md"
              aria-label="Upload resume file"
              disabled={uploading}
            >
              <FaUpload /> Upload Resume
            </button>

            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              className="hidden"
              onChange={(e) => {
                const f = e.target.files?.[0];
                if (f) handleUploadFile(f);
                e.target.value = "";
              }}
            />
          </div>
        </div>

        {/* Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Left */}
          <div>
            <div className="bg-white rounded-2xl p-5 shadow-lg border border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">1. Resume</h3>
                  <p className="text-sm text-gray-500 mt-1">Paste parsed resume text (or upload a file / load sample).</p>
                </div>

                <div className="flex items-center gap-3">
                  <select onChange={handleSelectSaved} className="text-sm border rounded-lg px-3 py-1 bg-white hidden sm:block">
                    <option value="">Use saved resume...</option>
                    {savedResumes.map((r) => (
                      <option key={r.id} value={r.id}>
                        {r.filename} {r.primary_flag ? "(Primary)" : ""}
                      </option>
                    ))}
                  </select>

                  <div className="sm:hidden flex items-center gap-2">
                    <button onClick={handleLoadSampleAndAutoRun} className="px-3 py-1 rounded-full bg-indigo-50 text-indigo-700 text-sm" disabled={loading}>Sample</button>
                    <button onClick={onUploadButtonClick} className="px-3 py-1 rounded-full bg-white border text-sm" disabled={uploading}>Upload</button>
                  </div>
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between gap-4">
                  <button
                    onClick={() => setPreviewOpen((s) => !s)}
                    className="text-sm text-indigo-700 font-medium hover:underline"
                    aria-expanded={previewOpen}
                  >
                    {previewOpen ? "Hide resume preview" : "Show resume preview"}
                  </button>

                  <div className="text-xs text-gray-500">{resumeCharCount.toLocaleString()} chars</div>
                </div>

                {previewOpen && (
                  <textarea
                    value={resumeText}
                    onChange={(e) => setResumeText(e.target.value)}
                    rows={12}
                    className="mt-3 w-full rounded-xl border border-gray-100 p-4 text-sm shadow-sm focus:ring-2 focus:ring-indigo-200 resize-y"
                    placeholder="Paste resume text here (contact info, summary, skills, experience bullets, education)..."
                    aria-label="Resume text"
                  />
                )}

                <div className="mt-3 text-xs text-gray-500 flex items-center justify-between">
                  <div>Tip: include a Skills section formatted as bullet points or comma-separated tags.</div>
                  <div>
                    {uploading ? (
                      <span className="inline-flex items-center gap-2 text-sm text-gray-600"><FaSpinner className="animate-spin" /> Uploading...</span>
                    ) : null}
                  </div>
                </div>
              </div>
            </div>

            {/* JD card */}
            <div className="mt-6 bg-white rounded-2xl p-5 shadow-lg border border-gray-100">
              <div className="flex items-start justify-between">
                <div>
                  <h3 className="text-lg font-semibold text-gray-800">2. Job Description</h3>
                  <p className="text-sm text-gray-500 mt-1">Paste the full job description you want to target. Include Requirements & Skills sections.</p>
                </div>

                <div className="text-xs text-gray-400">{jdWordCount} words</div>
              </div>

              <textarea
                id="jd-input"
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
                rows={12}
                className="mt-4 w-full rounded-xl border border-gray-100 p-4 text-sm shadow-sm focus:ring-2 focus:ring-indigo-200 resize-y"
                placeholder="Paste job description here..."
                aria-label="Job description"
              />

              <div className="mt-4 flex items-center justify-between text-xs text-gray-500">
                <div>Tip: highlight MUST HAVE skills in the JD for better tier detection.</div>
                <div />
              </div>
            </div>
          </div>

          {/* Right */}
          <aside className="sticky top-28">
            <div className="bg-white rounded-2xl p-6 shadow-lg border border-gray-100">
              <div className="mb-4">
                <h4 className="text-sm text-gray-500">Quick Preview</h4>
                <p className="text-lg font-semibold text-gray-900">Snapshot & actions</p>
              </div>

              <div className="mb-4">
                <Gauge value={0} />
              </div>

              <div className="space-y-3">
                <button
                  onClick={handleAnalyzeClick}
                  disabled={loading}
                  className="w-full inline-flex items-center justify-center gap-3 px-4 py-3 rounded-full bg-gradient-to-r from-indigo-600 to-blue-500 text-white font-semibold shadow-xl hover:from-indigo-700 hover:to-blue-600 transform transition"
                >
                  {loading ? <><FaSpinner className="animate-spin" /> Calculating...</> : <>Calculate Score <FaArrowRight /></>}
                </button>

                <button
                  onClick={handleLoadSampleAndAutoRun}
                  disabled={loading}
                  className="w-full inline-flex items-center justify-center gap-2 px-4 py-2 rounded-lg border border-gray-100 bg-white text-sm"
                >
                  Load sample & auto-run
                </button>

                <div className="pt-2 text-xs text-gray-500">
                  Results open in a dedicated dashboard with detailed recommendations.
                </div>
              </div>
            </div>

            <div className="mt-6 text-center text-sm text-gray-500">We analyze Structure · Keywords · Semantics · Readability · Tone</div>
          </aside>
        </div>

        {/* error area */}
        {error && (
          <div className="mt-6 max-w-3xl mx-auto text-center text-sm text-red-700 bg-red-50 p-3 rounded">
            {error}
          </div>
        )}
      </div>
    </div>
  );
}
