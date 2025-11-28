import React, { useState, useRef, useEffect } from "react";
import { FaMicrophone, FaPaperPlane } from "react-icons/fa";

/**
 * AnswerBar
 * Props:
 *  - onSubmit(text)  => called when user submits
 *  - placeholder
 */
export default function AnswerBar({ onSubmit, placeholder = "Type your answer..." }) {
  const [text, setText] = useState("");
  const inputRef = useRef(null);

  // keyboard shortcut: Enter to send (Shift+Enter for newline)
  useEffect(() => {
    const handler = (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        if (text.trim()) {
          handleSend();
        }
      }
    };
    const el = inputRef.current;
    if (el) el.addEventListener("keydown", handler);
    return () => {
      if (el) el.removeEventListener("keydown", handler);
    };
  }, [text]);

  const handleSend = () => {
    if (!text.trim()) return;
    onSubmit(text.trim());
    setText("");
  };

  return (
    <div className="fixed bottom-6 left-0 right-0 flex justify-center pointer-events-auto">
      <div className="max-w-4xl w-full px-6">
        <div className="bg-white border rounded-3xl p-3 flex items-center gap-3 shadow-lg">
          <button
            aria-label="Record voice (not enabled)"
            className="text-gray-400 hover:text-gray-600 p-2"
            title="Record (coming soon)"
          >
            <FaMicrophone />
          </button>

          <textarea
            ref={inputRef}
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder={placeholder}
            rows={2}
            className="flex-1 resize-none px-4 py-3 rounded-xl border focus:outline-none focus:ring-2 focus:ring-indigo-500"
            aria-label="Answer input"
          />

          <button
            onClick={handleSend}
            aria-label="Submit answer"
            className="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-3 rounded-xl flex items-center gap-3"
          >
            <FaPaperPlane /> <span className="hidden md:inline">Send</span>
          </button>
        </div>
      </div>
    </div>
  );
}
