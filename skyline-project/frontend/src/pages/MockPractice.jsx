import React, { useState, useEffect } from 'react';
import axios from 'axios';
import {
  FaUserTie,
  FaSlidersH,
  FaFileAlt,
  FaPlay,
  FaCheckCircle,
  FaMicrophone,
  FaPaperPlane,
  FaClock
} from 'react-icons/fa';
import toast from 'react-hot-toast';
import { motion } from 'framer-motion';

function MockPractice() {
  const [mode, setMode] = useState('setup'); // setup | intro | interview | analyzing | result | completed

  // Session State
  const [sessionId, setSessionId] = useState(null);
  const [sessionConfig, setSessionConfig] = useState({
    target_role: '',
    difficulty: 'Medium',
    question_count: 5,
    resume_id: ''
  });
  const [resumes, setResumes] = useState([]);

  // Interview State
  const [currentQuestion, setCurrentQuestion] = useState(null);
  const [userAnswer, setUserAnswer] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [feedback, setFeedback] = useState(null); // Shows after answer submission

  // Report State (new)
  const [report, setReport] = useState(null);

  // Load Resumes
  useEffect(() => {
    axios.get('/api/profile/resumes')
      .then(res => setResumes(res.data || []))
      .catch((err) => {
        console.error("Failed to load resumes", err);
      });
  }, []);

  // --- ACTIONS ---

  const handleStartSetup = async () => {
    if (!sessionConfig.target_role) return toast.error("Role is required");
    try {
      const res = await axios.post('/api/mock-v2/start-session', {
        ...sessionConfig,
        resume_id: sessionConfig.resume_id ? parseInt(sessionConfig.resume_id) : null
      });
      setSessionId(res.data.id);
      toast.success("Session created");
      setMode('intro');
    } catch (err) {
      console.error('Start session error', err);
      toast.error("Start failed");
    }
  };

  const handleStartInterview = () => {
    setMode('interview');
    fetchNextQuestion();
  };

  const fetchNextQuestion = async () => {
    if (!sessionId) return toast.error("Session not initialized");
    setIsLoading(true);
    setFeedback(null);
    setUserAnswer('');

    try {
      const res = await axios.post(`/api/mock-v2/${sessionId}/next`);
      // Backend may return { status: 'completed' } OR the exchange payload
      if (res.data?.status === 'completed') {
        // trigger report generation/analyze step
        await generateReport();
      } else {
        // Expected payload shape: { status: 'in_progress', question_id, question_text, current_index, total_questions }
        setCurrentQuestion(res.data);
      }
    } catch (err) {
      console.error("Error fetching question", err);
      toast.error("Error fetching question");
    } finally {
      setIsLoading(false);
    }
  };

  const handleSubmitAnswer = async () => {
    if (!currentQuestion) return toast.error("No active question");
    if (!userAnswer.trim()) return toast.error("Please answer the question!");
    setIsLoading(true);
    setFeedback(null);

    try {
      const res = await axios.post('/api/mock-v2/submit-answer', {
        exchange_id: currentQuestion.question_id,
        user_answer: userAnswer
      });
      // Expect response with micro-feedback in res.data.feedback (string)
      setFeedback(res.data.feedback ?? "No feedback returned.");
    } catch (err) {
      console.error("Submission error", err);
      toast.error("Submission failed");
    } finally {
      setIsLoading(false);
    }
  };

  // --- Generate Report (finalize session & fetch results) ---
  const generateReport = async () => {
    if (!sessionId) return toast.error("No session to analyze");
    setMode('analyzing');
    try {
      // Ask backend to finalize and run LLM scoring
      await axios.post(`/api/mock-v2/${sessionId}/end`);
      // Fetch results
      const res = await axios.get(`/api/mock-v2/${sessionId}/results`);
      setReport(res.data);
      setMode('result');
    } catch (err) {
      console.error("Report generation failed", err);
      toast.error("Analysis failed.");
      // fallback to completed if analysis fails but session ended
      setMode('completed');
    }
  };

  // --- RENDERERS ---

  // 1) SETUP
  if (mode === 'setup') {
    return (
      <div className="min-h-screen bg-gray-50 p-6 flex items-center justify-center">
        <div className="max-w-4xl w-full bg-white rounded-2xl shadow-xl flex overflow-hidden animate-fade-in-up">
          <div className="md:w-1/3 w-1/3 bg-indigo-600 p-8 text-white flex flex-col justify-between relative overflow-hidden">
            <div className="relative z-10">
              <h1 className="text-3xl font-bold mb-2">Mock Interview V2</h1>
              <p className="text-indigo-200">Master your next interview with AI-driven adaptive practice.</p>
            </div>
            <div className="relative z-10 space-y-4 mt-8">
              <div className="flex items-center gap-3">
                <div className="bg-indigo-500 p-2 rounded-lg"><FaUserTie /></div>
                <span className="text-sm font-medium">Role-Specific Questions</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="bg-indigo-500 p-2 rounded-lg"><FaSlidersH /></div>
                <span className="text-sm font-medium">Adaptive Difficulty</span>
              </div>
              <div className="flex items-center gap-3">
                <div className="bg-indigo-500 p-2 rounded-lg"><FaCheckCircle /></div>
                <span className="text-sm font-medium">Real-time Feedback</span>
              </div>
            </div>
            <div className="absolute -bottom-10 -right-10 w-40 h-40 bg-indigo-500 rounded-full opacity-50 blur-2xl"></div>
          </div>

          <div className="md:w-2/3 w-2/3 p-8 md:p-12">
            <h2 className="text-2xl font-bold text-gray-800 mb-6">Configure Session</h2>
            <div className="space-y-6">
              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2">Target Role</label>
                <input 
                  type="text" 
                  value={sessionConfig.target_role}
                  onChange={(e) => setSessionConfig({...sessionConfig, target_role: e.target.value})}
                  placeholder="e.g. Senior Frontend Developer"
                  className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500 outline-none transition"
                />
              </div>

              <div className="grid grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-bold text-gray-700 mb-2">Difficulty</label>
                  <select 
                    value={sessionConfig.difficulty}
                    onChange={(e) => setSessionConfig({...sessionConfig, difficulty: e.target.value})}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option>Easy</option>
                    <option>Medium</option>
                    <option>Hard</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-bold text-gray-700 mb-2">Question Count</label>
                  <select 
                    value={sessionConfig.question_count}
                    onChange={(e) => setSessionConfig({...sessionConfig, question_count: parseInt(e.target.value)})}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500 bg-white"
                  >
                    <option value="3">3 (Quick)</option>
                    <option value="5">5 (Standard)</option>
                    <option value="8">8 (Deep Dive)</option>
                  </select>
                </div>
              </div>

              <div>
                <label className="block text-sm font-bold text-gray-700 mb-2 flex items-center gap-2">
                  <FaFileAlt className="text-gray-400"/> Personalize with Resume?
                </label>
                {resumes.length > 0 ? (
                  <select 
                    value={sessionConfig.resume_id}
                    onChange={(e) => setSessionConfig({...sessionConfig, resume_id: e.target.value})}
                    className="w-full p-3 border rounded-xl focus:ring-2 focus:ring-indigo-500 bg-white text-sm"
                  >
                    <option value="">No, use generic questions</option>
                    {resumes.map(r => (
                      <option key={r.id} value={r.id}>{r.filename} {r.primary_flag ? '(Primary)' : ''}</option>
                    ))}
                  </select>
                ) : (
                  <div className="p-3 bg-gray-50 text-gray-500 text-sm rounded-lg border border-dashed">
                    No resumes found. Upload one in Profile to enable personalization.
                  </div>
                )}
              </div>

              <button 
                onClick={handleStartSetup}
                className="w-full mt-4 bg-indigo-600 text-white text-lg font-bold py-4 rounded-xl hover:bg-indigo-700 transition transform hover:scale-[1.02] shadow-lg flex items-center justify-center gap-2"
              >
                <FaPlay size={16} /> Create Session
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  // 2) INTRO
  if (mode === 'intro') {
    return (
      <div className="min-h-screen bg-gray-900 text-white flex flex-col items-center justify-center p-6 text-center">
        <motion.div initial={{ scale: 0.9, opacity: 0 }} animate={{ scale: 1, opacity: 1 }} className="max-w-xl">
          <div className="w-20 h-20 bg-indigo-500 rounded-full flex items-center justify-center mx-auto mb-6 text-3xl">
            <FaUserTie />
          </div>
          <h1 className="text-4xl font-bold mb-4">Get Ready!</h1>
          <p className="text-xl text-gray-300 mb-8">
            You are about to start a <strong>{sessionConfig.difficulty}</strong> interview for the position of <strong>{sessionConfig.target_role}</strong>.
          </p>
          <div className="flex gap-4 justify-center text-sm text-gray-400 mb-10">
            <span>• {sessionConfig.question_count} Questions</span>
            <span>• AI Evaluation</span>
            <span>• Real-time Feedback</span>
          </div>
          <button 
            onClick={handleStartInterview}
            className="px-10 py-4 bg-white text-indigo-900 font-bold rounded-full text-lg hover:scale-105 transition shadow-lg flex items-center gap-2 mx-auto"
          >
            <FaPlay /> Start Interview
          </button>
        </motion.div>
      </div>
    );
  }

  // 3) INTERVIEW LOOP
  if (mode === 'interview') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col">
        {/* Progress Bar */}
        <div className="h-2 bg-gray-200 w-full">
          <div 
            className="h-full bg-indigo-600 transition-all duration-500" 
            style={{ width: currentQuestion ? `${(currentQuestion.current_index / currentQuestion.total_questions) * 100}%` : '0%' }}
          ></div>
        </div>

        <div className="flex-grow flex flex-col md:flex-row max-w-7xl mx-auto w-full p-6 gap-6">
          
          {/* Left: Info Panel */}
          <div className="md:w-1/4 space-y-6">
            <div className="bg-white p-6 rounded-xl shadow-sm border">
               <h3 className="text-gray-400 uppercase text-xs font-bold tracking-wider">Question</h3>
               <p className="text-4xl font-bold text-indigo-600">
                 {currentQuestion ? currentQuestion.current_index : 0}
                 <span className="text-lg text-gray-400 font-normal">/{currentQuestion ? currentQuestion.total_questions : 0}</span>
               </p>
            </div>
            <div className="bg-white p-6 rounded-xl shadow-sm border flex items-center gap-3">
               <FaClock className="text-gray-400" />
               <span className="font-mono text-xl text-gray-700">00:00</span>
            </div>
          </div>

          {/* Right: Interaction Area */}
          <div className="md:w-3/4 flex flex-col gap-6">
            
            {/* AI Question Bubble */}
            <motion.div 
               key={currentQuestion?.question_id || 'idle'}
               initial={{ opacity: 0, y: 10 }} 
               animate={{ opacity: 1, y: 0 }}
               className="bg-white p-8 rounded-2xl shadow-sm border-l-4 border-indigo-600"
            >
              <h2 className="text-2xl font-medium text-gray-800 leading-relaxed">
                {isLoading && !currentQuestion ? "Generating question..." : currentQuestion?.question_text ?? "Waiting for question..."}
              </h2>
            </motion.div>

            {/* User Answer Input */}
            {!feedback ? (
              <div className="bg-white p-6 rounded-2xl shadow-sm border flex-grow flex flex-col">
                <textarea 
                  value={userAnswer}
                  onChange={(e) => setUserAnswer(e.target.value)}
                  placeholder="Type your answer here..."
                  className="w-full flex-grow p-4 bg-gray-50 border rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 resize-none"
                  autoFocus
                ></textarea>
                <div className="flex justify-between items-center mt-4">
                  <button className="text-gray-400 hover:text-gray-600"><FaMicrophone size={20}/></button>
                  <button 
                    onClick={handleSubmitAnswer} 
                    disabled={isLoading}
                    className="bg-indigo-600 text-white px-8 py-3 rounded-xl font-bold hover:bg-indigo-700 transition flex items-center gap-2"
                  >
                    {isLoading ? "Analyzing..." : "Submit Answer"} <FaPaperPlane />
                  </button>
                </div>
              </div>
            ) : (
              // Feedback Overlay
              <motion.div 
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-indigo-900 text-white p-8 rounded-2xl shadow-xl flex-grow flex flex-col justify-center items-center text-center"
              >
                <div className="bg-green-500 p-3 rounded-full mb-4"><FaCheckCircle size={32} /></div>
                <h3 className="text-2xl font-bold mb-2">Answer Recorded</h3>
                <div className="bg-white/10 p-6 rounded-xl mb-6 max-w-2xl text-lg leading-relaxed">
                  "{feedback}"
                </div>
                <div className="flex gap-4">
                  <button 
                    onClick={() => {
                      setFeedback(null);
                      setUserAnswer('');
                      fetchNextQuestion();
                    }}
                    className="bg-white text-indigo-900 px-6 py-3 rounded-full font-bold hover:scale-105 transition shadow-lg"
                  >
                    Next Question →
                  </button>

                  <button
                    onClick={() => {
                      // Optionally allow user to edit and re-submit (stay on same question)
                      setFeedback(null);
                    }}
                    className="px-6 py-3 rounded-full border border-white text-white hover:bg-white/10 transition"
                  >
                    Edit Answer
                  </button>
                </div>
              </motion.div>
            )}

          </div>
        </div>
      </div>
    );
  }

  // 4) ANALYZING (waiting for generateReport)
  if (mode === 'analyzing') {
    return (
      <div className="min-h-screen bg-gray-50 flex flex-col items-center justify-center p-6 text-center">
        <div className="w-24 h-24 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mb-6"></div>
        <h2 className="text-2xl font-bold text-gray-800">Generating Performance Report...</h2>
        <p className="text-gray-500 mt-2">AI is analyzing your transcript, detecting strengths, and grading your answers.</p>
      </div>
    );
  }

  // 5) RESULT (show report)
  if (mode === 'result' && report) {
    return (
      <div className="min-h-screen bg-gray-50 p-6 md:p-10">
        <div className="max-w-6xl mx-auto space-y-8">
          
          {/* Header */}
          <div className="flex justify-between items-center">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">Interview Results</h1>
              <p className="text-gray-500">Role: {sessionConfig.target_role}</p>
            </div>
            <button onClick={() => setMode('setup')} className="bg-white border border-gray-300 text-gray-700 px-6 py-2 rounded-lg hover:bg-gray-50">
              Back to Dashboard
            </button>
          </div>

          {/* Top Row: Score & Dimensions */}
          <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
            {/* Overall Score */}
            <div className="bg-white p-8 rounded-2xl shadow-sm border flex flex-col items-center justify-center text-center">
               <h3 className="text-gray-400 font-bold uppercase tracking-wider text-sm mb-4">Overall Score</h3>
               <div className="relative w-40 h-40 flex items-center justify-center">
                 <svg className="w-full h-full" viewBox="0 0 36 36">
                    <path className="text-gray-100" d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
                    <path className="text-indigo-600" strokeDasharray={`${report.overall_score}, 100`} d="M18 2.0845 a 15.9155 15.9155 0 0 1 0 31.831 a 15.9155 15.9155 0 0 1 0 -31.831" fill="none" stroke="currentColor" strokeWidth="3" />
                 </svg>
                 <span className="absolute text-4xl font-bold text-indigo-900">{report.overall_score}</span>
               </div>
            </div>

            {/* Dimension Bars */}
            <div className="md:col-span-2 bg-white p-8 rounded-2xl shadow-sm border">
               <h3 className="font-bold text-gray-800 mb-6">Performance Breakdown</h3>
               <div className="space-y-4">
                 {Object.entries(report.dimensions).map(([key, score]) => (
                   <div key={key}>
                     <div className="flex justify-between text-sm font-medium mb-1">
                       <span className="text-gray-600">{key}</span>
                       <span className="text-gray-900">{score}%</span>
                     </div>
                     <div className="w-full bg-gray-100 rounded-full h-2.5">
                       <div className="bg-indigo-600 h-2.5 rounded-full" style={{ width: `${score}%` }}></div>
                     </div>
                   </div>
                 ))}
               </div>
            </div>
          </div>

          {/* Insights Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
             {/* Strengths */}
             <div className="bg-green-50 p-6 rounded-2xl border border-green-100">
               <h3 className="font-bold text-green-800 mb-4 flex items-center gap-2"><FaCheckCircle /> Strengths</h3>
               <ul className="space-y-2">
                 {report.feedback?.strengths?.map((s, i) => (
                   <li key={i} className="flex items-start gap-2 text-green-700 text-sm">
                     <span className="mt-1">•</span> {s}
                   </li>
                 )) ?? <li className="text-sm text-gray-500">No strengths detected.</li>}
               </ul>
             </div>

             {/* Weaknesses / Quick Wins */}
             <div className="bg-white p-6 rounded-2xl border shadow-sm">
               <h3 className="font-bold text-gray-800 mb-4">⚡ Quick Wins</h3>
               <ul className="space-y-3">
                 {report.feedback?.quick_wins?.map((win, i) => (
                   <li key={i} className="p-3 bg-indigo-50 rounded-lg border border-indigo-100">
                     <strong className="block text-indigo-900 text-sm mb-1">{win.title}</strong>
                     <p className="text-xs text-indigo-700">{win.description}</p>
                   </li>
                 )) ?? <li className="text-sm text-gray-500">No quick wins suggested.</li>}
               </ul>
             </div>
          </div>

          {/* NEW: Detailed Transcript & Improvements */}
          <div className="bg-white rounded-2xl shadow-sm border overflow-hidden">
            <div className="p-6 border-b bg-gray-50">
               <h3 className="font-bold text-gray-800 text-lg">📝 Detailed Transcript & Improvements</h3>
               <p className="text-sm text-gray-500">Compare your answers with AI-suggested improvements.</p>
            </div>
            
            <div className="divide-y">
              {report.transcript?.map((item, i) => (
                <div key={i} className="p-6 hover:bg-gray-50 transition">
                  {/* Question */}
                  <div className="mb-4">
                    <span className="text-xs font-bold text-indigo-500 uppercase tracking-wider">Question {i + 1}</span>
                    <h4 className="text-lg font-medium text-gray-900 mt-1">{item.question}</h4>
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                    {/* User Answer */}
                    <div className="bg-red-50 p-4 rounded-xl border border-red-100">
                      <h5 className="text-sm font-bold text-red-800 mb-2 flex items-center gap-2">
                         ❌ Your Answer
                      </h5>
                      <p className="text-gray-700 text-sm whitespace-pre-wrap">{item.user_answer || "(No answer provided)"}</p>
                      <div className="mt-3 pt-3 border-t border-red-200">
                         <p className="text-xs text-red-700 italic">Feedback: {item.feedback}</p>
                      </div>
                    </div>

                    {/* AI Improved Answer */}
                    <div className="bg-green-50 p-4 rounded-xl border border-green-100">
                      <h5 className="text-sm font-bold text-green-800 mb-2 flex items-center gap-2">
                         ✅ AI Suggested Answer
                      </h5>
                      <p className="text-gray-800 text-sm whitespace-pre-wrap">{item.improved_answer}</p>
                      <div className="mt-3 text-right">
                         <button 
                           onClick={() => {navigator.clipboard.writeText(item.improved_answer); toast.success("Copied!");}}
                           className="text-xs text-green-700 font-bold hover:underline"
                         >
                           Copy to Clipboard
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

  // 6) COMPLETED fallback
  if (mode === 'completed') {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-3xl font-bold text-gray-800">Interview Complete! 🎉</h1>
          <p className="text-gray-600 mt-4">Well done — you can run another simulation or review your session in the dashboard.</p>
          <div className="mt-6 flex gap-3 justify-center">
            <button onClick={() => { setMode('setup'); setSessionId(null); setCurrentQuestion(null); }} className="px-6 py-3 bg-indigo-600 text-white rounded-xl">New Session</button>
          </div>
        </div>
      </div>
    );
  }

  return null;
}

export default MockPractice;
