// frontend/src/components/Sidebar.jsx

import React from 'react';
import { Link } from 'react-router-dom';
import { FaTachometerAlt, FaBriefcase, FaFileAlt, FaRobot, FaQuestionCircle, FaLightbulb, FaLinkedin, FaEnvelope, FaPhone } from 'react-icons/fa';

const ProfilePlaceholder = () => (
    <svg className="w-full h-full text-gray-300" fill="currentColor" viewBox="0 0 24 24">
        <path d="M24 20.993V24H0v-2.996A14.977 14.977 0 0112.004 15c4.904 0 9.26 2.354 11.996 5.993zM16.002 8.999a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
);

const moduleIcons = [
    { name: 'Dashboard', path: '/', icon: <FaTachometerAlt /> },
    { name: 'Jobs', path: '/jobs', icon: <FaBriefcase /> },
    { name: 'Resume', path: '/resume', icon: <FaFileAlt /> },
    { name: 'ATS', path: '/ats', icon: <FaRobot /> },
    { name: 'Mock', path: '/mock-test', icon: <FaQuestionCircle /> },
    { name: 'Assistant', path: '/assistant', icon: <FaLightbulb /> },
];

function Sidebar({ onEditProfileClick, userProfile }) {
    const skillsArray = userProfile.skills ? userProfile.skills.split(',').map(skill => skill.trim()).filter(skill => skill) : [];

    return (
        // This is the main flex container for the sidebar. It takes the full height of its parent.
        <div className="flex flex-col w-80 bg-gray-800 text-white flex-shrink-0">
            
            {/* This div wraps all content that is NOT the footer. `flex-grow` is the key. */}
            <div className="flex-grow p-6 overflow-y-auto">
                <div className="flex flex-col items-center text-center">
                    <div className="w-24 h-24 rounded-full bg-gray-700 overflow-hidden mb-4">
                        <ProfilePlaceholder />
                    </div>
                    <h3 className="text-xl font-semibold">{userProfile.fullName || 'Your Name'}</h3>
                </div>

                <div className="mt-6 text-sm text-left">
                    {userProfile.email && <p className="text-gray-400 flex items-center mb-2"><FaEnvelope className="mr-3 flex-shrink-0" /> {userProfile.email}</p>}
                    {userProfile.phone && <p className="text-gray-400 flex items-center mb-2"><FaPhone className="mr-3 flex-shrink-0" /> {userProfile.phone}</p>}
                    {userProfile.linkedin && <a href={`https://${userProfile.linkedin}`} target="_blank" rel="noopener noreferrer" className="text-gray-400 flex items-center hover:text-indigo-400"><FaLinkedin className="mr-3 flex-shrink-0" /> LinkedIn Profile</a>}
                </div>

                {skillsArray.length > 0 && (
                    <div className="mt-6 text-left">
                        <h4 className="font-semibold mb-2">Skills</h4>
                        <div className="flex flex-wrap gap-2">
                            {skillsArray.map((skill, index) => (
                                <span key={index} className="px-2 py-1 text-xs font-medium bg-gray-700 text-indigo-300 rounded-full">{skill}</span>
                            ))}
                        </div>
                    </div>
                )}

                <button
                    onClick={onEditProfileClick}
                    className="mt-6 w-full px-4 py-2 text-sm font-medium text-white bg-indigo-600 rounded-lg hover:bg-indigo-700"
                >
                    Edit Profile
                </button>
            </div>

            {/* This is the footer. It will always be at the bottom because the div above uses `flex-grow`. */}
            <div className="p-6 border-t border-gray-700">
                <div className="grid grid-cols-3 gap-4">
                    {moduleIcons.map((item) => (
                        <Link
                            key={item.name}
                            to={item.path}
                            className="flex flex-col items-center justify-center p-3 bg-gray-700 rounded-lg hover:bg-indigo-600 aspect-square transition-colors duration-200"
                        >
                            <div className="text-xl">{item.icon}</div>
                            <span className="text-xs mt-2 text-center">{item.name}</span>
                        </Link>
                    ))}
                </div>
            </div>
        </div>
    );
}

export default Sidebar;