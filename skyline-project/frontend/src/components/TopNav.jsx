import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { FaUserCircle, FaBars, FaTimes, FaRobot, FaCog, FaSignOutAlt, FaUser } from 'react-icons/fa';
import { motion, AnimatePresence } from 'framer-motion';

const NAV_ITEMS = [
  { label: 'Dashboard', path: '/' },
  { label: 'Job Aggregator', path: '/jobs' },
  { label: 'Resume Generator', path: '/resume' },
  { label: 'ATS Checker', path: '/ats' },
  { label: 'Mock Practice', path: '/mock' },
  { label: 'AI Assistant', path: '/ai' }, // New dedicated route
];

function TopNav() {
  const [isProfileOpen, setIsProfileOpen] = useState(false);
  const [isMobileMenuOpen, setIsMobileMenuOpen] = useState(false);
  const location = useLocation();

  const isActive = (path) => location.pathname === path;

  return (
    <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-gray-200 shadow-sm">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          
          {/* 1. Logo Section */}
          <div className="flex-shrink-0 flex items-center gap-2 cursor-pointer">
            <div className="bg-indigo-600 text-white font-bold text-lg p-1.5 rounded-lg shadow-sm">S</div>
            <span className="text-xl font-bold text-gray-900 tracking-tight">Skyline</span>
          </div>

          {/* 2. Desktop Navigation (Center) */}
          <nav className="hidden md:flex space-x-1 relative">
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                className={`relative px-3 py-2 text-sm font-medium transition-colors duration-200 rounded-md ${
                  isActive(item.path) 
                    ? 'text-indigo-600' 
                    : 'text-gray-600 hover:text-indigo-600 hover:bg-gray-50'
                }`}
              >
                {item.label}
                {isActive(item.path) && (
                  <motion.div
                    layoutId="underline"
                    className="absolute left-0 right-0 bottom-0 h-0.5 bg-indigo-600"
                  />
                )}
              </Link>
            ))}
          </nav>

          {/* 3. Right Section: User Avatar & Mobile Toggle */}
          <div className="flex items-center gap-4">
            
            {/* User Dropdown */}
            <div className="relative">
              <button 
                onClick={() => setIsProfileOpen(!isProfileOpen)}
                className="flex items-center gap-2 focus:outline-none"
              >
                <div className="w-9 h-9 rounded-full bg-indigo-100 border border-indigo-200 flex items-center justify-center text-indigo-700 hover:ring-2 hover:ring-indigo-100 transition">
                  {/* In a real app, use an <img> here */}
                  <span className="font-bold text-sm">US</span>
                </div>
              </button>

              <AnimatePresence>
                {isProfileOpen && (
                  <motion.div 
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: 10 }}
                    className="absolute right-0 mt-2 w-56 bg-white rounded-xl shadow-xl border border-gray-100 py-2 origin-top-right ring-1 ring-black ring-opacity-5"
                  >
                    <div className="px-4 py-3 border-b border-gray-100 mb-1">
                      <p className="text-sm font-medium text-gray-900">Demo User</p>
                      <p className="text-xs text-gray-500 truncate">user@example.com</p>
                    </div>
                    
                    <Link 
                      to="/profile" 
                      onClick={() => setIsProfileOpen(false)}
                      className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-600"
                    >
                      <FaUser className="mr-3 text-gray-400" /> View Profile
                    </Link>
                    <a href="#" className="flex items-center px-4 py-2 text-sm text-gray-700 hover:bg-indigo-50 hover:text-indigo-600">
                      <FaCog className="mr-3 text-gray-400" /> Settings
                    </a>
                    
                    <div className="border-t border-gray-100 my-1"></div>
                    
                    <button className="flex w-full items-center px-4 py-2 text-sm text-red-600 hover:bg-red-50">
                      <FaSignOutAlt className="mr-3 text-red-400" /> Sign Out
                    </button>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Mobile Hamburger */}
            <div className="md:hidden">
              <button onClick={() => setIsMobileMenuOpen(!isMobileMenuOpen)} className="text-gray-600 hover:text-indigo-600 p-2">
                {isMobileMenuOpen ? <FaTimes size={24} /> : <FaBars size={24} />}
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Mobile Menu (Collapse) */}
      <AnimatePresence>
        {isMobileMenuOpen && (
          <motion.div 
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="md:hidden bg-white border-t border-gray-100 overflow-hidden"
          >
            <div className="px-2 pt-2 pb-3 space-y-1 sm:px-3">
              {NAV_ITEMS.map((item) => (
                <Link
                  key={item.path}
                  to={item.path}
                  onClick={() => setIsMobileMenuOpen(false)}
                  className={`block px-3 py-2 rounded-md text-base font-medium ${
                    isActive(item.path)
                      ? 'bg-indigo-50 text-indigo-600'
                      : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                  }`}
                >
                  {item.label}
                </Link>
              ))}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

export default TopNav;