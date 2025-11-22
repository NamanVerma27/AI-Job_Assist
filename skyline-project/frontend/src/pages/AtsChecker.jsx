import React, { useState } from 'react';
import axios from 'axios';
import { FaCheckCircle, FaExclamationTriangle, FaMagic } from 'react-icons/fa';

function AtsChecker() {
  const [step, setStep] = useState('input'); // input | loading | result
  const [resumeText, setResumeText] = useState('');
  const [jdText, setJdText] = useState('');
  const [report, setReport] = useState(null);

  const handleAnalyze = async () => {
    if (!resumeText || !jdText) {
      alert("Please provide both Resume text and Job Description.");
      return;
    }

    setStep('loading');
    try {
      const res = await axios.post('/api/resume/ats-score', {
        resume_text: resumeText,
        jd_text: jdText
      });
      setReport(res.data.data);
      setStep('result');
    } catch (err) {
      alert("Analysis failed. Please try again.");
      setStep('input');
    }
  };

  // --- SCORE COLOR HELPER ---
  const getScoreColor = (score) => {
    if (score >= 80) return "text-green-600 border-green-500 bg-green-50";
    if (score >= 50) return "text-yellow-600 border-yellow-500 bg-yellow-50";
    return "text-red-600 border-red-500 bg-red-50";
  };

  return (
    <div className="p-10 min-h-screen bg-gray-50">
      <div className="max-w-5xl mx-auto">
        <h1 className="text-3xl font-bold text-gray-800 mb-2">ATS Score Checker</h1>
        <p className="text-gray-600 mb-8">
          See how well your resume matches the job description using AI & Keyword analysis.
        </p>

        {step === 'input' && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* Input Resume */}
            <div className="bg-white p-6 rounded-lg shadow-sm border">
              <h3 className="font-bold text-lg mb-3">1. Paste Resume Text</h3>
              <textarea
                className="w-full h-64 p-3 border rounded focus:ring-2 focus:ring-indigo-500"
                placeholder="Copy and paste your resume content here..."
                value={resumeText}
                onChange={(e) => setResumeText(e.target.value)}
              ></textarea>
            </div>

            {/* Input JD */}
            <div className="bg-white p-6 rounded-lg shadow-sm border">
              <h3 className="font-bold text-lg mb-3">2. Paste Job Description</h3>
              <textarea
                className="w-full h-64 p-3 border rounded focus:ring-2 focus:ring-indigo-500"
                placeholder="Copy and paste the job description here..."
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              ></textarea>
            </div>

            <div className="col-span-1 md:col-span-2 text-center">
              <button
                onClick={handleAnalyze}
                className="bg-indigo-600 text-white text-xl font-bold px-10 py-4 rounded-full shadow-lg hover:bg-indigo-700 transition transform hover:scale-105"
              >
                Calculate Score
              </button>
            </div>
          </div>
        )}

        {step === 'loading' && (
          <div className="text-center py-20">
            <div className="animate-spin rounded-full h-16 w-16 border-b-4 border-indigo-600 mx-auto mb-6"></div>
            <h2 className="text-2xl font-semibold text-gray-700">Analyzing Keywords & Context...</h2>
          </div>
        )}

        {step === 'result' && report && (
          <div className="space-y-8 animate-fade-in">
            {/* Score Banner */}
            <div className="bg-white p-8 rounded-xl shadow-lg border-l-8 border-indigo-600 flex flex-col md:flex-row items-center justify-between">
              <div>
                <h2 className="text-2xl font-bold text-gray-800">Overall Match Score</h2>
                <p className="text-gray-500 mt-1">{report.summary}</p>
              </div>
              <div className={`mt-4 md:mt-0 relative w-32 h-32 rounded-full border-4 flex items-center justify-center text-4xl font-bold ${getScoreColor(report.total_score)}`}>
                {report.total_score}%
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Missing Keywords */}
              <div className="bg-white p-6 rounded-lg shadow-sm border">
                <h3 className="text-lg font-bold text-red-600 mb-4 flex items-center gap-2">
                  <FaExclamationTriangle /> Missing Keywords
                </h3>
                <div className="flex flex-wrap gap-2">
                  {report.missing_keywords.length > 0 ? (
                    report.missing_keywords.map((word, i) => (
                      <span key={i} className="bg-red-50 text-red-700 px-3 py-1 rounded-full text-sm border border-red-200">
                        {word}
                      </span>
                    ))
                  ) : (
                    <p className="text-green-600">Great! No major keywords missing.</p>
                  )}
                </div>
              </div>

              {/* AI Improvements */}
              <div className="bg-white p-6 rounded-lg shadow-sm border">
                <h3 className="text-lg font-bold text-indigo-600 mb-4 flex items-center gap-2">
                  <FaMagic /> AI Recommendations
                </h3>
                <ul className="space-y-3">
                  {report.improvements.map((tip, i) => (
                    <li key={i} className="flex items-start gap-2 text-gray-700">
                      <FaCheckCircle className="text-green-500 mt-1 flex-shrink-0" />
                      {tip}
                    </li>
                  ))}
                </ul>
              </div>
            </div>

            <div className="text-center">
              <button
                onClick={() => setStep('input')}
                className="text-indigo-600 font-semibold hover:underline"
              >
                Check Another Resume
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default AtsChecker;