import React, { useState, useRef, useEffect } from 'react';
import axios from 'axios';
import { FaPaperPlane, FaRobot, FaUserTie, FaBriefcase, FaMicrophone } from 'react-icons/fa';
import ReactMarkdown from 'react-markdown';

function MockPractice() {
  const [mode, setMode] = useState('setup'); // 'setup' | 'interview'
  const [targetRole, setTargetRole] = useState('');
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const startInterview = async () => {
    if (!targetRole.trim()) return;
    setMode('interview');
    setIsLoading(true);
    setMessages([]); // Clear previous chat

    try {
      // Trigger the AI to start
      const res = await axios.post('/api/ai/generate', {
        prompt: `I am ready to start my interview for the position of ${targetRole}. Start by welcoming me and asking the first question.`,
        context: "mock_interview",
        role: targetRole
      });
      setMessages([{ sender: 'ai', text: res.data.data }]);
    } catch (err) {
      setMessages([{ sender: 'ai', text: "Could not start interview. Check backend." }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    const userMsg = { sender: 'user', text: input };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setIsLoading(true);

    try {
      const res = await axios.post('/api/ai/generate', {
        prompt: userMsg.text,
        context: "mock_interview",
        role: targetRole
      });
      setMessages(prev => [...prev, { sender: 'ai', text: res.data.data }]);
    } catch (err) {
      setMessages(prev => [...prev, { sender: 'ai', text: "Error fetching feedback." }]);
    } finally {
      setIsLoading(false);
    }
  };

  // --- RENDER SETUP ---
  if (mode === 'setup') {
    return (
      <div className="p-10 min-h-screen bg-gray-50 flex flex-col items-center justify-center">
        <div className="max-w-2xl w-full bg-white p-10 rounded-2xl shadow-xl text-center">
          <div className="bg-indigo-100 w-20 h-20 mx-auto rounded-full flex items-center justify-center mb-6">
            <FaUserTie className="text-4xl text-indigo-600" />
          </div>
          <h1 className="text-4xl font-bold text-gray-800 mb-4">Mock Interview Simulator</h1>
          <p className="text-lg text-gray-600 mb-8">
            Master your next interview. Choose a role, answer real-time questions, and get instant feedback on your answers.
          </p>
          
          <div className="relative max-w-md mx-auto mb-8">
            <FaBriefcase className="absolute left-4 top-4 text-gray-400 text-lg" />
            <input 
              type="text" 
              value={targetRole}
              onChange={(e) => setTargetRole(e.target.value)}
              placeholder="Target Role (e.g. Senior Java Dev)" 
              className="w-full pl-12 p-4 text-lg border-2 border-gray-200 rounded-xl focus:border-indigo-600 focus:outline-none transition"
            />
          </div>

          <button 
            onClick={startInterview}
            disabled={!targetRole}
            className="w-full max-w-md bg-indigo-600 text-white text-xl font-bold py-4 rounded-xl hover:bg-indigo-700 disabled:opacity-50 transition shadow-lg"
          >
            Start Simulation
          </button>
        </div>
      </div>
    );
  }

  // --- RENDER INTERVIEW ---
  return (
    <div className="p-6 h-screen flex flex-col bg-gray-100">
      {/* Header */}
      <div className="bg-white p-4 rounded-t-xl shadow-sm flex justify-between items-center border-b">
        <div className="flex items-center gap-3">
          <div className="bg-indigo-600 p-2 rounded-lg text-white"><FaRobot size={24}/></div>
          <div>
            <h2 className="text-xl font-bold text-gray-800">{targetRole} Interview</h2>
            <p className="text-sm text-green-600 flex items-center gap-1">● Live Session</p>
          </div>
        </div>
        <button onClick={() => setMode('setup')} className="text-gray-500 hover:text-red-600 font-medium">
          Exit Session
        </button>
      </div>

      {/* Chat Area */}
      <div className="flex-grow bg-white overflow-y-auto p-6 space-y-6">
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.sender === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div className={`max-w-[80%] p-5 rounded-2xl text-md leading-relaxed shadow-sm ${
              msg.sender === 'user' 
                ? 'bg-indigo-600 text-white rounded-br-none' 
                : 'bg-gray-50 text-gray-800 border rounded-bl-none'
            }`}>
              <strong className="block text-xs mb-1 opacity-70 uppercase tracking-wide">
                {msg.sender === 'ai' ? 'Interviewer' : 'You'}
              </strong>
              <ReactMarkdown>{msg.text}</ReactMarkdown>
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex gap-2 text-gray-400 items-center ml-2">
            <span className="animate-bounce">●</span>
            <span className="animate-bounce delay-100">●</span>
            <span className="animate-bounce delay-200">●</span>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className="bg-white p-4 rounded-b-xl border-t shadow-sm">
        <form onSubmit={handleSend} className="flex gap-3 max-w-5xl mx-auto">
          <input 
            type="text" 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your answer..." 
            className="flex-grow p-4 bg-gray-50 border border-gray-200 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500 text-lg"
          />
          <button type="submit" disabled={isLoading} className="bg-indigo-600 text-white px-8 rounded-xl hover:bg-indigo-700 transition shadow-md">
            <FaPaperPlane size={20} />
          </button>
        </form>
      </div>
    </div>
  );
}

export default MockPractice;