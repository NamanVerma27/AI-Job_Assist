// frontend/src/pages/JobAggregator.jsx

import React, { useState } from 'react';
import axios from 'axios';
import JobCard from '../components/JobCard';
import FilterSidebar from '../components/FilterSidebar';

function JobAggregator() {
  const [jobs, setJobs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  const [filters, setFilters] = useState({
    query: '',
    location: '',
    company: '',
    days_old: 0,
  });

  const handleFilterChange = (name, value) => {
    // If we're changing the main search query, we want to update it directly
    if (name === 'query') {
      setFilters(prevFilters => ({ ...prevFilters, [name]: value }));
    } else {
      // For the sidebar filters, we also update the state
      setFilters(prevFilters => ({ ...prevFilters, [name]: value }));
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    setIsLoading(true);
    setError(null);
    setJobs([]);

    try {
      // Build the query parameters string from the filters state
      const params = new URLSearchParams();
      if (filters.query) params.append('query', filters.query);
      if (filters.location) params.append('location', filters.location);
      if (filters.company) params.append('company', filters.company);
      if (filters.days_old > 0) params.append('days_old', filters.days_old);

      const response = await axios.get(`http://127.0.0.1:8000/jobs?${params.toString()}`);
      
      if (response.data && response.data.length > 0) {
        setJobs(response.data);
      } else {
        setError('No jobs found for your search criteria.');
      }
    } catch (err) {
      setError('Failed to fetch jobs. An API might be down. Please try again later.');
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="p-10">
      <h1 className="text-3xl font-bold text-gray-800">Intelligent Job Aggregator</h1>
      <p className="mt-2 text-md text-gray-600">Combine your search with powerful filters to find the perfect job.</p>
      
      {/* Main Search Bar */}
      <form onSubmit={handleSearch} className="mt-8 flex gap-4">
        <input 
          type="text"
          value={filters.query}
          onChange={(e) => handleFilterChange('query', e.target.value)}
          placeholder="Search by keyword or job title (e.g., Senior Python Developer)"
          className="flex-grow p-3 border border-gray-300 rounded-lg shadow-sm"
        />
        <button 
          type="submit" 
          disabled={isLoading}
          className="px-6 py-3 bg-indigo-600 text-white font-semibold rounded-lg shadow-md hover:bg-indigo-700"
        >
          {isLoading ? 'Searching...' : 'Search'}
        </button>
      </form>

      {/* Main Content Area: Results Grid + Filter Sidebar */}
      <div className="mt-10 grid grid-cols-12 gap-8">
        
        {/* Job Results (Left Side) */}
        <div className="col-span-8">
          {isLoading && <p className="text-center text-lg font-semibold text-gray-600">Fetching the latest jobs...</p>}
          {error && <p className="text-center text-lg font-semibold text-red-500">{error}</p>}
          
          {jobs.length > 0 && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {jobs.map((job) => (
                <JobCard key={`${job.id}-${job.source}`} job={job} />
              ))}
            </div>
          )}
        </div>

        {/* Filter Sidebar (Right Side) */}
        <div className="col-span-4">
          <FilterSidebar 
            filters={filters}
            onFilterChange={handleFilterChange}
            onApplyFilters={handleSearch} // The "Apply" button also triggers the search
          />
        </div>

      </div>
    </div>
  );
}

export default JobAggregator;