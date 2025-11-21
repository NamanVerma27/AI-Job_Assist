import React, { useState } from 'react';
import { Routes, Route } from 'react-router-dom';
import axios from 'axios';
import Sidebar from './components/Sidebar';
import Navbar from './components/Navbar';
import ProfileModal from './components/ProfileModal';
import Dashboard from './pages/Dashboard';
import JobAggregator from './pages/JobAggregator';
import ResumeGenerator from './pages/ResumeGenerator';
import Footer from './components/Footer';

function App() {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [userProfile, setUserProfile] = useState({ fullName: '', email: '', phone: '', linkedin: '', skills: '' });

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setUserProfile(prevState => ({ ...prevState, [name]: value }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    axios.post('http://127.0.0.1:8000/profile', userProfile)
      .then(response => {
        alert(response.data.message);
        setIsModalOpen(false);
      })
      .catch(error => {
        console.error('Error saving profile:', error);
        alert('Error: Could not save profile.');
      });
  };

  return (
    <div className="bg-gray-100 h-screen flex flex-col">
      <Navbar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar onEditProfileClick={() => setIsModalOpen(true)} userProfile={userProfile} />
        <div className="flex-1 flex flex-col overflow-y-auto">
          <main className="flex-grow">
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/jobs" element={<JobAggregator />} />
              <Route path="/resume" element={<ResumeGenerator />} />
            </Routes>
          </main>
          <Footer />
        </div>
      </div>
      <ProfileModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        profile={userProfile}
        handleInputChange={handleInputChange}
        handleSubmit={handleSubmit}
      />
    </div>
  );
}

export default App;