// frontend/src/components/ResumeTemplates.jsx

import React from 'react';

// In a real app, these templates would be more complex Markdown strings
const templates = [
  { id: 1, name: 'Modern', content: '# John Doe\n\n*Your modern resume starts here.*' },
  { id: 2, name: 'Classic', content: '## Jane Smith\n\n_A classic and professional resume._' },
  { id: 3, name: 'Creative', content: '### Your Name\n\n> A creative resume to stand out.' },
  { id: 4, name: 'Technical', content: '## Tech Guru\n\n`Skills: Python, React, AWS`' },
];

function ResumeTemplates({ onSelectTemplate }) {
  const [selectedId, setSelectedId] = useState(null);

  const handleSelect = () => {
    const selected = templates.find(t => t.id === selectedId);
    if (selected) {
      onSelectTemplate(selected.content);
    }
  };

  return (
    <div>
      <h3 className="text-2xl font-bold text-center text-gray-800 mb-6">Choose a Starting Point</h3>
      <div className="grid grid-cols-2 gap-6">
        {templates.map(template => (
          <div
            key={template.id}
            onClick={() => setSelectedId(template.id)}
            className={`p-6 border-2 rounded-lg cursor-pointer transition-all duration-200 ${
              selectedId === template.id ? 'border-indigo-500 scale-105' : 'border-gray-300'
            }`}
          >
            <h4 className="text-lg font-semibold">{template.name}</h4>
          </div>
        ))}
      </div>
      {selectedId && (
        <div className="text-center mt-8">
          <button 
            onClick={handleSelect}
            className="px-8 py-3 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700"
          >
            Select Template
          </button>
        </div>
      )}
    </div>
  );
}

// We need to import useState at the top
import { useState } from 'react';
export default ResumeTemplates;