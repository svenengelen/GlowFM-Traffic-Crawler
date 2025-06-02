import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [trafficData, setTrafficData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    roads: [],
    cities: [],
    minDelay: ''
  });
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const TARGET_ROADS = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270"];
  const TARGET_CITIES = [
    "Eindhoven", "Venlo", "Weert", "'s-Hertogenbosch", "Roermond", "Maasbracht",
    "Nijmegen", "Oss", "Zonzeel", "Breda", "Tilburg", "Rotterdam", "Deurne",
    "Helmond", "Venray", "Heerlen", "Maastricht", "Belgische Grens", "Duitse Grens", 
    "Valkenswaard"
  ];

  const DELAY_OPTIONS = [
    { value: 1, label: '1+ minutes' },
    { value: 5, label: '5+ minutes' },
    { value: 10, label: '10+ minutes' },
    { value: 15, label: '15+ minutes' },
    { value: 20, label: '20+ minutes' },
    { value: 25, label: '25+ minutes' },
    { value: 30, label: '30+ minutes' }
  ];

  const fetchTrafficData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      if (filters.roads.length > 0) {
        params.append('roads', filters.roads.join(','));
      }
      if (filters.cities.length > 0) {
        params.append('cities', filters.cities.join(','));
      }
      if (filters.minDelay) {
        params.append('min_delay', filters.minDelay);
      }

      const response = await axios.get(`${API}/traffic?${params.toString()}`);
      setTrafficData(response.data);
      setLastUpdated(new Date(response.data.last_updated));
    } catch (err) {
      setError('Failed to fetch traffic data');
      console.error('Error fetching traffic data:', err);
    } finally {
      setLoading(false);
    }
  };

  const refreshData = async () => {
    try {
      setRefreshing(true);
      await axios.post(`${API}/refresh`);
      await fetchTrafficData();
    } catch (err) {
      setError('Failed to refresh data');
      console.error('Error refreshing data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleRoadFilter = (road) => {
    setFilters(prev => ({
      ...prev,
      roads: prev.roads.includes(road) 
        ? prev.roads.filter(r => r !== road)
        : [...prev.roads, road]
    }));
  };

  const handleCityFilter = (city) => {
    setFilters(prev => ({
      ...prev,
      cities: prev.cities.includes(city)
        ? prev.cities.filter(c => c !== city)
        : [...prev.cities, city]
    }));
  };

  const handleDelayFilter = (delay) => {
    setFilters(prev => ({
      ...prev,
      minDelay: prev.minDelay === delay ? '' : delay
    }));
  };

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const diff = Math.floor((new Date() - timestamp) / 1000);
    if (diff < 60) return `${diff} seconds ago`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minutes ago`;
    return `${Math.floor(diff / 3600)} hours ago`;
  };

  const getDelayColor = (delayMinutes) => {
    if (delayMinutes >= 30) return 'text-red-600 bg-red-50';
    if (delayMinutes >= 15) return 'text-orange-600 bg-orange-50';
    if (delayMinutes >= 5) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  useEffect(() => {
    fetchTrafficData();
  }, [filters]);

  useEffect(() => {
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchTrafficData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [filters]);

  if (loading && !trafficData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading traffic data...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900">ANWB Traffic Monitor</h1>
              <p className="text-sm text-gray-600">
                Real-time traffic jams and speed cameras in the Netherlands
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                Last updated: {formatTimeAgo(lastUpdated)}
              </div>
              <button
                onClick={refreshData}
                disabled={refreshing}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {refreshing ? 'Refreshing...' : 'Refresh'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        {trafficData && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-gray-900">{trafficData.filtered_jams}</div>
              <div className="text-sm text-gray-600">Active Traffic Jams</div>
              {trafficData.total_jams !== trafficData.filtered_jams && (
                <div className="text-xs text-gray-500">
                  of {trafficData.total_jams} total
                </div>
              )}
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-gray-900">{trafficData.speed_cameras.length}</div>
              <div className="text-sm text-gray-600">Speed Cameras</div>
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-gray-900">{TARGET_ROADS.length}</div>
              <div className="text-sm text-gray-600">Monitored Roads</div>
            </div>
          </div>
        )}

        {/* Filters */}
        <div className="bg-white rounded-lg shadow mb-8">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Filters</h2>
            
            {/* Road Filters */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Roads</h3>
              <div className="flex flex-wrap gap-2">
                {TARGET_ROADS.map(road => (
                  <button
                    key={road}
                    onClick={() => handleRoadFilter(road)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      filters.roads.includes(road)
                        ? 'bg-blue-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {road}
                  </button>
                ))}
              </div>
            </div>

            {/* City Filters */}
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-700 mb-3">Cities</h3>
              <div className="flex flex-wrap gap-2">
                {TARGET_CITIES.map(city => (
                  <button
                    key={city}
                    onClick={() => handleCityFilter(city)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      filters.cities.includes(city)
                        ? 'bg-green-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {city}
                  </button>
                ))}
              </div>
            </div>

            {/* Delay Filters */}
            <div>
              <h3 className="text-sm font-medium text-gray-700 mb-3">Minimum Delay</h3>
              <div className="flex flex-wrap gap-2">
                {DELAY_OPTIONS.map(option => (
                  <button
                    key={option.value}
                    onClick={() => handleDelayFilter(option.value)}
                    className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                      filters.minDelay === option.value
                        ? 'bg-red-600 text-white'
                        : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                    }`}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-8">
            <div className="text-red-800">{error}</div>
          </div>
        )}

        {/* Traffic Jams */}
        {trafficData && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h2 className="text-lg font-semibold text-gray-900">Traffic Jams</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {trafficData.traffic_jams.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    No traffic jams found matching your filters
                  </div>
                ) : (
                  trafficData.traffic_jams.map((jam, index) => (
                    <div key={jam.id || index} className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3">
                            <span className="bg-blue-100 text-blue-800 text-xs font-semibold px-2.5 py-0.5 rounded">
                              {jam.road}
                            </span>
                            {jam.delay_minutes > 0 && (
                              <span className={`text-xs font-semibold px-2.5 py-0.5 rounded ${getDelayColor(jam.delay_minutes)}`}>
                                +{jam.delay_minutes} min
                              </span>
                            )}
                            {jam.length_km > 0 && (
                              <span className="bg-gray-100 text-gray-800 text-xs font-semibold px-2.5 py-0.5 rounded">
                                {jam.length_km} km
                              </span>
                            )}
                          </div>
                          <div className="mt-2">
                            <p className="text-sm font-medium text-gray-900">{jam.location}</p>
                            <div className="flex items-center space-x-4 mt-1 text-xs text-gray-500">
                              {jam.delay_text && <span>{jam.delay_text}</span>}
                              {jam.length_text && <span>{jam.length_text}</span>}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>

            {/* Speed Cameras */}
            <div className="bg-white rounded-lg shadow">
              <div className="p-6 border-b">
                <h2 className="text-lg font-semibold text-gray-900">Speed Cameras</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {trafficData.speed_cameras.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    No speed cameras found matching your filters
                  </div>
                ) : (
                  trafficData.speed_cameras.map((camera, index) => (
                    <div key={camera.id || index} className="p-6">
                      <div className="flex items-start space-x-3">
                        <span className="bg-red-100 text-red-800 text-xs font-semibold px-2.5 py-0.5 rounded">
                          {camera.road}
                        </span>
                        <div className="flex-1">
                          <p className="text-sm font-medium text-gray-900">{camera.location}</p>
                          {camera.direction && (
                            <p className="text-xs text-gray-500 mt-1">{camera.direction}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;
