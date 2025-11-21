// frontend/src/components/AiAssistantView.jsx
import React from 'react';
import { FaPaperPlane } from 'react-icons/fa';

function AiAssistantView() {
  return (
    <div className="flex flex-col h-full">
      <h3 className="text-2xl font-semibold text-gray-800 mb-4">AI Assistant</h3>
      {/* Message display area */}
      <div className="flex-grow bg-gray-50 rounded-lg p-4 border overflow-y-auto">
         <div className="p-3 rounded-lg bg-indigo-100 text-gray-800 max-w-xs">
            Hello! How can I help you prepare for your career today?
         </div>
      </div>
      {/* Input area */}
      <div className="mt-4 flex">
        <input type="text" placeholder="Ask about interview questions, skills, etc..." className="flex-grow border rounded-l-lg p-3 focus:outline-none focus:ring-2 focus:ring-indigo-500" />
        <button className="bg-indigo-600 text-white px-4 rounded-r-lg hover:bg-indigo-700">
          <FaPaperPlane />
        </button>
      </div>
    </div>
  );
}
export default AiAssistantView;