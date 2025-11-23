import React from 'react';
import { FaPlus, FaTrash } from 'react-icons/fa';

function ExperienceTab({ experience, onChange }) {
  const addExp = () => {
    onChange([...experience, { title: '', company: '', start_date: '', description: '' }]);
  };

  const removeExp = (index) => {
    const newExp = [...experience];
    newExp.splice(index, 1);
    onChange(newExp);
  };

  const updateExp = (index, field, value) => {
    const newExp = [...experience];
    newExp[index][field] = value;
    onChange(newExp);
  };

  return (
    <div className="space-y-6 animate-fade-in">
      {experience.map((exp, i) => (
        <div key={i} className="p-6 bg-white rounded-xl border shadow-sm relative group">
          <button 
            onClick={() => removeExp(i)} 
            className="absolute top-4 right-4 text-gray-300 hover:text-red-500 transition"
          >
            <FaTrash />
          </button>

          <h3 className="text-sm font-bold text-gray-400 uppercase tracking-wide mb-4">Position {i + 1}</h3>
          
          <div className="grid grid-cols-2 gap-4 mb-4">
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1">Job Title</label>
              <input 
                type="text" value={exp.title} 
                onChange={(e) => updateExp(i, 'title', e.target.value)}
                className="w-full p-2 border rounded focus:ring-indigo-500"
                placeholder="e.g. Senior Developer"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1">Company</label>
              <input 
                type="text" value={exp.company} 
                onChange={(e) => updateExp(i, 'company', e.target.value)}
                className="w-full p-2 border rounded focus:ring-indigo-500"
                placeholder="e.g. Google"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1">Start Date</label>
              <input 
                type="text" value={exp.start_date} 
                onChange={(e) => updateExp(i, 'start_date', e.target.value)}
                className="w-full p-2 border rounded focus:ring-indigo-500"
                placeholder="2022"
              />
            </div>
            <div>
              <label className="block text-xs font-bold text-gray-500 mb-1">End Date</label>
              <input 
                type="text" value={exp.end_date || ''} 
                onChange={(e) => updateExp(i, 'end_date', e.target.value)}
                className="w-full p-2 border rounded focus:ring-indigo-500"
                placeholder="Present"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-bold text-gray-500 mb-1">Description</label>
            <textarea 
              rows="3" 
              value={exp.description || ''} 
              onChange={(e) => updateExp(i, 'description', e.target.value)}
              className="w-full p-2 border rounded focus:ring-indigo-500"
              placeholder="Describe your role and achievements..."
            ></textarea>
          </div>
        </div>
      ))}

      <button 
        onClick={addExp}
        className="w-full py-3 border-2 border-dashed border-indigo-200 text-indigo-600 font-bold rounded-xl hover:bg-indigo-50 transition flex items-center justify-center gap-2"
      >
        <FaPlus /> Add Position
      </button>
    </div>
  );
}

export default ExperienceTab;