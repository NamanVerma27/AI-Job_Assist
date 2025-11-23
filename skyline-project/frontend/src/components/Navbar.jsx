import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { FaUserCircle, FaBars } from 'react-icons/fa';

function Navbar() {
  const [isMenuOpen, setIsMenuOpen] = useState(false);

  return (
    <nav className="bg-white shadow-sm border-b px-6 py-3 flex justify-between items-center z-50 relative">
      {/* Logo */}
      <div className="flex items-center gap-2">
        <div className="bg-indigo-600 text-white font-bold text-xl p-2 rounded-lg">S</div>
        <span className="text-xl font-bold text-gray-800 tracking-tight">Skyline</span>
      </div>

      {/* Right Side: User Menu */}
      <div className="relative">
        <button 
          onClick={() => setIsMenuOpen(!isMenuOpen)}
          className="flex items-center gap-2 hover:bg-gray-100 p-2 rounded-lg transition"
        >
          <span className="text-sm font-medium text-gray-700 hidden md:block">Demo User</span>
          <FaUserCircle className="text-2xl text-gray-500" />
        </button>

        {/* Dropdown */}
        {isMenuOpen && (
          <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border py-2 animate-fade-in-down">
            <Link 
              to="/profile" 
              onClick={() => setIsMenuOpen(false)}
              className="block px-4 py-2 text-gray-700 hover:bg-indigo-50 hover:text-indigo-600"
            >
              My Profile
            </Link>
            <div className="border-t my-1"></div>
            <button 
              className="block w-full text-left px-4 py-2 text-red-600 hover:bg-red-50"
              onClick={() => alert("Logout logic here")}
            >
              Sign Out
            </button>
          </div>
        )}
      </div>
    </nav>
  );
}

export default Navbar;