// frontend/src/pages/ResumeGenerator.jsx

import React, { useState, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import { useDropzone } from 'react-dropzone';
import jsPDF from 'jspdf';
import html2canvas from 'html2canvas';
import ResumeTemplates from '../components/ResumeTemplates';

const ResumeTabCard = ({ title, subtitle, onClick, isActive }) => {
  const baseClasses = "w-full text-left p-6 bg-white rounded-lg shadow-md transition-all duration-300 transform cursor-pointer";
  const activeClasses = "scale-105 shadow-xl border-b-4 border-indigo-600";
  const inactiveClasses = "hover:shadow-lg hover:-translate-y-1";
  return <div onClick={onClick} className={`${baseClasses} ${isActive ? activeClasses : inactiveClasses}`}><h2 className="text-xl font-semibold text-gray-700">{title}</h2><p className="mt-2 text-sm text-gray-500">{subtitle}</p></div>;
};

// --- Main Page Component ---
function ResumeGenerator() {
  const [activeTab, setActiveTab] = useState('yourResumes');
  const [userResumes, setUserResumes] = useState([]); // Will hold uploaded resumes
  const [selectedResume, setSelectedResume] = useState(null);
  const [editorContent, setEditorContent] = useState(''); // State for the markdown editor
  const previewRef = useRef(null); // Ref to capture the preview panel for PDF export

  // --- File Upload Logic ---
  const onDrop = (acceptedFiles) => {
    const file = acceptedFiles[0];
    const reader = new FileReader();
    reader.onload = () => {
      const newResume = {
        id: Date.now(),
        name: file.name,
        content: `New Upload: ${file.name}`, // Placeholder content, actual parsing is complex
        lastModified: new Date().toLocaleDateString(),
      };
      setUserResumes(prev => [newResume, ...prev]);
      setSelectedResume(newResume);
    };
    reader.readAsDataURL(file);
  };
  const { getRootProps, getInputProps } = useDropzone({ onDrop, accept: { 'application/pdf': ['.pdf'], 'application/vnd.openxmlformats-officedocument.wordprocessingml.document': ['.docx'], 'application/msword': ['.doc'] } });

  // --- Navigation and Action Handlers ---
  const handleEditResume = () => {
    if (selectedResume) {
      setEditorContent(selectedResume.content);
      setActiveTab('generate');
    }
  };

  const handleSelectTemplate = (templateContent) => {
    setEditorContent(templateContent);
    setActiveTab('generate');
  };

  const handleExportPdf = () => {
    const input = previewRef.current;
    html2canvas(input, { scale: 2 }).then((canvas) => {
      const imgData = canvas.toDataURL('image/png');
      const pdf = new jsPDF('p', 'mm', 'a4');
      const pdfWidth = pdf.internal.pageSize.getWidth();
      const pdfHeight = pdf.internal.pageSize.getHeight();
      const canvasWidth = canvas.width;
      const canvasHeight = canvas.height;
      const ratio = Math.min(pdfWidth / canvasWidth, pdfHeight / canvasHeight);
      const imgX = (pdfWidth - canvasWidth * ratio) / 2;
      const imgY = 0;
      pdf.addImage(imgData, 'PNG', imgX, imgY, canvasWidth * ratio, canvasHeight * ratio);
      pdf.save("resume.pdf");
    });
  };

  // --- Render Functions for Each Tab ---
  const renderYourResumes = () => (
    <div className="flex h-[70vh]">
      <div className="w-1/3 pr-8 overflow-y-auto">
        <h3 className="text-2xl font-bold text-gray-800 mb-4">Your Saved Resumes</h3>
        <div {...getRootProps()} className="border-2 border-dashed border-gray-400 rounded-lg p-6 text-center cursor-pointer hover:bg-gray-50 mb-4">
          <input {...getInputProps()} />
          <p className="text-indigo-600 font-semibold">+ Add or Drop Resume</p>
          <p className="text-xs text-gray-500">.pdf, .doc, .docx</p>
        </div>
        {userResumes.length > 0 ? (
          <div className="space-y-4">{userResumes.map(r => (
            <div key={r.id} onClick={() => setSelectedResume(r)} className={`p-4 rounded-lg cursor-pointer ${selectedResume?.id === r.id ? 'bg-indigo-100' : 'bg-white'}`}>
              <p className="font-semibold">{r.name}</p><p className="text-xs text-gray-500">{r.lastModified}</p>
            </div>
          ))}</div>
        ) : (
          <p className="text-center text-gray-500 mt-8">No resumes uploaded/saved yet.</p>
        )}
      </div>
      <div className="w-2/3 bg-gray-200 rounded-lg p-4 flex flex-col">
        {selectedResume ? (
          <>
            <div ref={previewRef} className="flex-grow bg-white p-8 shadow-inner"><ReactMarkdown>{selectedResume.content}</ReactMarkdown></div>
            <button onClick={handleEditResume} className="mt-4 px-6 py-2 bg-indigo-600 text-white font-semibold rounded-lg self-center">Edit Resume</button>
          </>
        ) : (
          <div className="w-full h-full flex items-center justify-center"><p className="text-gray-500">Upload or select a resume to preview.</p></div>
        )}
      </div>
    </div>
  );

  const renderGenerateResume = () => (
    <div className="space-y-6">
      <div className="relative p-4 border rounded-lg">
        <input type="text" placeholder="Paste a job URL to get AI suggestions..." className="w-full p-2 border-b-2 focus:outline-none" />
        {/* We'll add the loading/generate button logic later */}
      </div>
      <div className="grid grid-cols-2 gap-8 h-[60vh]">
        <div>
          <h3 className="text-xl font-bold mb-2">Edit Palette (Markdown)</h3>
          <textarea value={editorContent} onChange={(e) => setEditorContent(e.target.value)} className="w-full h-full p-4 border rounded-lg resize-none font-mono"></textarea>
        </div>
        <div>
          <div className="flex justify-between items-center mb-2">
            <h3 className="text-xl font-bold">Preview Palette</h3>
            <button onClick={handleExportPdf} className="px-4 py-2 bg-green-600 text-white rounded-lg">Export as PDF</button>
          </div>
          <div ref={previewRef} className="w-full h-full p-8 border rounded-lg bg-white overflow-y-auto"><ReactMarkdown>{editorContent}</ReactMarkdown></div>
        </div>
      </div>
    </div>
  );

  const renderTemplates = () => (
    <ResumeTemplates onSelectTemplate={handleSelectTemplate} />
  );

  const renderContent = () => {
    switch (activeTab) {
      case 'yourResumes': return renderYourResumes();
      case 'generate': return renderGenerateResume();
      case 'templates': return renderTemplates();
      default: return null;
    }
  };

  return (
    <div className="p-10">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-8">
        <ResumeTabCard title="Your Resumes" subtitle="Upload and manage your documents" onClick={() => setActiveTab('yourResumes')} isActive={activeTab === 'yourResumes'}/>
        <ResumeTabCard title="Generate New Resume" subtitle="Create or edit with AI assistance" onClick={() => setActiveTab('generate')} isActive={activeTab === 'generate'}/>
        <ResumeTabCard title="Resume Templates" subtitle="Choose a professional layout" onClick={() => setActiveTab('templates')} isActive={activeTab === 'templates'}/>
      </div>
      <div className="mt-12">{renderContent()}</div>
    </div>
  );
}

export default ResumeGenerator;