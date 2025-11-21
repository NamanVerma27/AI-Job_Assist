// frontend/src/components/ProfileModal.jsx

import React from 'react';
import UserProfileForm from './UserProfileForm'; // We will reuse the form we already made

// We receive several props to control the modal
function ProfileModal({ isOpen, onClose, profile, handleInputChange, handleSubmit }) {
  if (!isOpen) {
    return null; // If it's not open, render nothing
  }

  return (
    // The semi-transparent backdrop
    <div className="fixed inset-0 bg-black bg-opacity-50 z-40 flex justify-center items-center">
      {/* The modal card itself */}
      <div className="bg-white rounded-lg shadow-xl p-8 w-full max-w-3xl z-50">
        {/* We pass all the necessary props down to the form */}
        <UserProfileForm
          profile={profile}
          handleInputChange={handleInputChange}
          handleSubmit={handleSubmit}
        />
        <div className="mt-4 flex justify-start">
           <button 
             onClick={onClose} 
             className="px-4 py-2 bg-gray-200 text-gray-800 rounded-md hover:bg-gray-300"
           >
             Cancel
           </button>
        </div>
      </div>
    </div>
  );
}

export default ProfileModal;