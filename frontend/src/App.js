import React, { useState, useEffect } from 'react';
import './App.css';

const API_BASE_URL = process.env.REACT_APP_BACKEND_URL || 'http://localhost:8001';

function App() {
  const [trafficJams, setTrafficJams] = useState([]);
  const [speedCameras, setSpeedCameras] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null);
  
  // Filter states
  const [selectedRoad, setSelectedRoad] = useState('');
  const [selectedCity, setSelectedCity] = useState('');
  const [selectedMinDelay, setSelectedMinDelay] = useState('');
  const [activeTab, setActiveTab] = useState('traffic'); // 'traffic' or 'cameras'
  
  // Available options
  const [availableRoads] = useState([
    'A2', 'A16', 'A50', 'A58', 'A59', 'A65', 'A67', 'A73', 'A76', 'A270', 'N2', 'N69', 'N266', 'N270'
  ]);
  const [availableCities] = useState([
    'Eindhoven', 'Venlo', 'Weert', "'s-Hertogenbosch", 'Roermond', 'Maasbracht',
    'Nijmegen', 'Oss', 'Zonzeel', 'Breda', 'Tilburg', 'Rotterdam', 'Deurne',
    'Helmond', 'Venray', 'Heerlen', 'Maastricht', 'Belgische Grens', 'Duitse Grens', 'Valkenswaard'
  ]);
  const [delayOptions] = useState([1, 5, 10, 15, 20, 25, 30]);

  // Fetch data functions
  const fetchTrafficJams = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedRoad) params.append('road', selectedRoad);
      if (selectedCity) params.append('city', selectedCity);
      if (selectedMinDelay) params.append('min_delay', selectedMinDelay);
      
      const response = await fetch(`${API_BASE_URL}/api/traffic-jams?${params}`);
      const data = await response.json();
      setTrafficJams(data.traffic_jams || []);
    } catch (error) {
      console.error('Error fetching traffic jams:', error);
      setTrafficJams([]);
    }
  };

  const fetchSpeedCameras = async () => {
    try {
      const params = new URLSearchParams();
      if (selectedRoad) params.append('road', selectedRoad);
      if (selectedCity) params.append('city', selectedCity);
      
      const response = await fetch(`${API_BASE_URL}/api/speed-cameras?${params}`);
      const data = await response.json();
      setSpeedCameras(data.speed_cameras || []);
    } catch (error) {
      console.error('Error fetching speed cameras:', error);
      setSpeedCameras([]);
    }
  };

  const fetchSummary = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/api/summary`);
      const data = await response.json();
      setSummary(data);
      if (data.last_updated) {
        setLastUpdated(new Date(data.last_updated));
      }
    } catch (error) {
      console.error('Error fetching summary:', error);
    }
  };

  const manualRefresh = async () => {
    setLoading(true);
    try {
      // Trigger manual scrape
      await fetch(`${API_BASE_URL}/api/scrape`, { method: 'POST' });
      
      // Wait a moment then refresh data
      setTimeout(async () => {
        await Promise.all([fetchTrafficJams(), fetchSpeedCameras(), fetchSummary()]);
        setLoading(false);
      }, 2000);
    } catch (error) {
      console.error('Error refreshing data:', error);
      setLoading(false);
    }
  };

  // Initial data load and auto-refresh
  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      await Promise.all([fetchTrafficJams(), fetchSpeedCameras(), fetchSummary()]);
      setLoading(false);
    };
    
    loadData();
    
    // Auto-refresh every 5 minutes
    const interval = setInterval(loadData, 300000);
    return () => clearInterval(interval);
  }, []);

  // Refresh data when filters change
  useEffect(() => {
    fetchTrafficJams();
    fetchSpeedCameras();
  }, [selectedRoad, selectedCity, selectedMinDelay]);

  const getDelayColorClass = (delayMinutes) => {
    if (delayMinutes >= 30) return 'text-red-700 bg-red-100';
    if (delayMinutes >= 15) return 'text-orange-700 bg-orange-100';
    if (delayMinutes >= 5) return 'text-yellow-700 bg-yellow-100';
    return 'text-green-700 bg-green-100';
  };

  const formatLastUpdated = (date) => {
    if (!date) return 'Never';
    return date.toLocaleString('nl-NL', {
      day: '2-digit',
      month: '2-digit',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-6">
            <div>
              <h1 className="text-3xl font-bold text-gray-900">ANWB Verkeer Monitor</h1>
              <p className="text-gray-600 mt-1">Live verkeersinformatie en flitsers</p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                <div>Laatste update: {formatLastUpdated(lastUpdated)}</div>
                <div className="flex items-center mt-1">
                  <div className={`w-2 h-2 rounded-full mr-2 ${summary?.scrape_success ? 'bg-green-500' : 'bg-red-500'}`}></div>
                  {summary?.scrape_success ? 'Verbonden' : 'Fout'}
                </div>
              </div>
              <button
                onClick={manualRefresh}
                disabled={loading}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-4 py-2 rounded-md text-sm font-medium transition-colors"
              >
                {loading ? 'Vernieuwen...' : 'Vernieuw'}
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Summary Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-red-100 rounded-md flex items-center justify-center">
                  <svg className="w-5 h-5 text-red-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7 4a1 1 0 11-2 0 1 1 0 012 0zm-1-9a1 1 0 00-1 1v4a1 1 0 102 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Actieve Files</p>
                <p className="text-2xl font-semibold text-gray-900">{summary?.total_jams || 0}</p>
              </div>
            </div>
          </div>
          
          <div className="bg-white rounded-lg shadow-sm p-6">
            <div className="flex items-center">
              <div className="flex-shrink-0">
                <div className="w-8 h-8 bg-blue-100 rounded-md flex items-center justify-center">
                  <svg className="w-5 h-5 text-blue-600" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4 4a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V6a2 2 0 00-2-2H4zm12 6a1 1 0 11-2 0 1 1 0 012 0zm-7-3a1 1 0 00-1 1v6a1 1 0 102 0V8a1 1 0 00-1-1z" clipRule="evenodd" />
                  </svg>
                </div>
              </div>
              <div className="ml-4">
                <p className="text-sm font-medium text-gray-600">Flitsers</p>
                <p className="text-2xl font-semibold text-gray-900">{summary?.total_cameras || 0}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-sm p-6 mb-8">
          <h2 className="text-lg font-medium text-gray-900 mb-4">Filters</h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            {/* Road Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Weg</label>
              <select
                value={selectedRoad}
                onChange={(e) => setSelectedRoad(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Alle wegen</option>
                {availableRoads.map(road => (
                  <option key={road} value={road}>{road}</option>
                ))}
              </select>
            </div>

            {/* City Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Plaats</label>
              <select
                value={selectedCity}
                onChange={(e) => setSelectedCity(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Alle plaatsen</option>
                {availableCities.map(city => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
            </div>

            {/* Delay Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min. vertraging</label>
              <select
                value={selectedMinDelay}
                onChange={(e) => setSelectedMinDelay(e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">Alle vertragingen</option>
                {delayOptions.map(delay => (
                  <option key={delay} value={delay}>{delay}+ minuten</option>
                ))}
              </select>
            </div>

            {/* Clear Filters */}
            <div className="flex items-end">
              <button
                onClick={() => {
                  setSelectedRoad('');
                  setSelectedCity('');
                  setSelectedMinDelay('');
                }}
                className="w-full bg-gray-100 hover:bg-gray-200 text-gray-700 px-3 py-2 rounded-md text-sm font-medium transition-colors"
              >
                Wis filters
              </button>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6">
          <div className="border-b border-gray-200">
            <nav className="-mb-px flex space-x-8">
              <button
                onClick={() => setActiveTab('traffic')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'traffic'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Verkeersinformatie ({trafficJams.length})
              </button>
              <button
                onClick={() => setActiveTab('cameras')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'cameras'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                Flitsers ({speedCameras.length})
              </button>
            </nav>
          </div>
        </div>

        {/* Content */}
        {activeTab === 'traffic' ? (
          /* Traffic Jams */
          <div className="bg-white rounded-lg shadow-sm">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">
                Actieve Files ({trafficJams.length})
              </h2>
            </div>
            
            {loading && (
              <div className="p-8 text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2 text-gray-600">Gegevens laden...</p>
              </div>
            )}
            
            {!loading && trafficJams.length === 0 && (
              <div className="p-8 text-center text-gray-500">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <p className="mt-2">Geen files gevonden met de huidige filters.</p>
              </div>
            )}
            
            {!loading && trafficJams.length > 0 && (
              <div className="divide-y divide-gray-200">
                {trafficJams.map((jam, index) => (
                  <div key={jam.id || index} className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 mr-3">
                            {jam.road}
                          </span>
                          <h3 className="text-lg font-medium text-gray-900">{jam.location}</h3>
                          {jam.city && (
                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                              {jam.city}
                            </span>
                          )}
                        </div>
                        <div className="mt-2 flex items-center space-x-4 text-sm text-gray-600">
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zm1-12a1 1 0 10-2 0v4a1 1 0 00.293.707l2.828 2.829a1 1 0 101.415-1.415L11 9.586V6z" clipRule="evenodd" />
                            </svg>
                            {jam.delay_text || `${jam.delay_minutes} min`}
                          </div>
                          <div className="flex items-center">
                            <svg className="w-4 h-4 mr-1" fill="currentColor" viewBox="0 0 20 20">
                              <path fillRule="evenodd" d="M5.05 4.05a7 7 0 119.9 9.9L10 18.9l-4.95-4.95a7 7 0 010-9.9zM10 11a2 2 0 100-4 2 2 0 000 4z" clipRule="evenodd" />
                            </svg>
                            {jam.length_km} km
                          </div>
                        </div>
                      </div>
                      <div className={`px-3 py-1 rounded-full text-xs font-medium ${getDelayColorClass(jam.delay_minutes)}`}>
                        {jam.delay_minutes} min
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          /* Speed Cameras */
          <div className="bg-white rounded-lg shadow-sm">
            <div className="p-6 border-b border-gray-200">
              <h2 className="text-lg font-medium text-gray-900">
                Flitsers ({speedCameras.length})
              </h2>
            </div>
            
            {loading && (
              <div className="p-8 text-center">
                <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                <p className="mt-2 text-gray-600">Gegevens laden...</p>
              </div>
            )}
            
            {!loading && speedCameras.length === 0 && (
              <div className="p-8 text-center text-gray-500">
                <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z" />
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 13a3 3 0 11-6 0 3 3 0 016 0z" />
                </svg>
                <p className="mt-2">Geen flitsers gevonden met de huidige filters.</p>
                <p className="text-sm text-gray-400 mt-1">Flitser data wordt nog geïmplementeerd.</p>
              </div>
            )}
            
            {!loading && speedCameras.length > 0 && (
              <div className="divide-y divide-gray-200">
                {speedCameras.map((camera, index) => (
                  <div key={camera.id || index} className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center">
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800 mr-3">
                            {camera.road}
                          </span>
                          <h3 className="text-lg font-medium text-gray-900">{camera.location}</h3>
                          {camera.city && (
                            <span className="ml-2 inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-gray-100 text-gray-800">
                              {camera.city}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center text-red-600">
                        <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                          <path fillRule="evenodd" d="M4 5a2 2 0 00-2 2v6a2 2 0 002 2h12a2 2 0 002-2V7a2 2 0 00-2-2H4zm12 12a5 5 0 11-10 0h10z" clipRule="evenodd" />
                        </svg>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
