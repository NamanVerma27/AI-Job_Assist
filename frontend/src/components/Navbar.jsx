// frontend/src/components/Navbar.jsx

import React from 'react';
// Import NavLink instead of Link
import { NavLink } from 'react-router-dom';

const navLinks = [
  { name: 'Dashboard', path: '/' },
  { name: 'Job Aggregator', path: '/jobs' },
  { name: 'Resume Generator', path: '/resume' },
  { name: 'ATS Score Checker', path: '/ats' },
  { name: 'Mock Practice', path: '/mock-test' },
  { name: 'AI Assistant', path: '/assistant' },
];

function Navbar() {
  // These are the base classes for every link
  const baseLinkClasses = "text-gray-600 hover:text-indigo-600 font-medium transition-colors duration-200";
  // These classes are ADDED only when the link is active
  const activeLinkClasses = "text-indigo-600 border-b-2 border-indigo-600 pb-1";

  return (
    <nav className="bg-white shadow-sm h-16 flex items-center justify-between px-8 flex-shrink-0">
      <div className="text-2xl font-bold text-indigo-600">
        Skyline
      </div>
      <div className="flex items-center space-x-8">
        {navLinks.map((link) => (
          // Use NavLink here
          <NavLink
            key={link.name}
            to={link.path}
            // The className prop can accept a function to check for active state
            className={({ isActive }) => 
              `${baseLinkClasses} ${isActive ? activeLinkClasses : ''}`
            }
          >
            {link.name}
          </NavLink>
        ))}
      </div>
    </nav>
  );
}

export default Navbar;