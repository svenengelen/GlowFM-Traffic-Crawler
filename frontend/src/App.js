import React, { useState, useEffect } from 'react';
import './App.css';

const DELAY_FILTERS = [
  { value: 1, label: '1+ min' },
  { value: 5, label: '5+ min' },
  { value: 10, label: '10+ min' },
  { value: 15, label: '15+ min' },
  { value: 20, label: '20+ min' },
  { value: 25, label: '25+ min' },
  { value: 30, label: '30+ min' }
];

function App() {
  const [trafficData, setTrafficData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [filters, setFilters] = useState({
    road: '',
    city: '',
    minDelay: ''
  });
  const [monitoredRoads, setMonitoredRoads] = useState([]);
  const [monitoredCities, setMonitoredCities] = useState([]);
  const [lastUpdated, setLastUpdated] = useState(null);
  const [activeTab, setActiveTab] = useState('traffic');

  const backendUrl = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

  // Fetch monitored roads and cities on component mount
  useEffect(() => {
    fetchMonitoredData();
  }, []);

  // Fetch traffic data when filters change
  useEffect(() => {
    fetchTrafficData();
  }, [filters]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(fetchTrafficData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [filters]);

  const fetchMonitoredData = async () => {
    try {
      const [roadsResponse, citiesResponse] = await Promise.all([
        fetch(`${backendUrl}/api/roads`),
        fetch(`${backendUrl}/api/cities`)
      ]);

      if (roadsResponse.ok && citiesResponse.ok) {
        const roadsData = await roadsResponse.json();
        const citiesData = await citiesResponse.json();
        setMonitoredRoads(roadsData.roads);
        setMonitoredCities(citiesData.cities);
      }
    } catch (err) {
      console.error('Error fetching monitored data:', err);
    }
  };

  const fetchTrafficData = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (filters.road) params.append('road', filters.road);
      if (filters.city) params.append('city', filters.city);
      if (filters.minDelay) params.append('min_delay', filters.minDelay);

      const response = await fetch(`${backendUrl}/api/traffic?${params.toString()}`);
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setTrafficData(data);
      setLastUpdated(new Date(data.last_updated));
    } catch (err) {
      console.error('Error fetching traffic data:', err);
      setError(`Fout bij ophalen van data: ${err.message}`);
    } finally {
      setLoading(false);
    }
  };

  const handleRefresh = async () => {
    setLoading(true);
    try {
      await fetch(`${backendUrl}/api/traffic/refresh`, { method: 'POST' });
      // Wait a moment for data to be processed
      setTimeout(fetchTrafficData, 2000);
    } catch (err) {
      setError(`Fout bij verversen van data: ${err.message}`);
    }
  };

  const handleFilterChange = (filterType, value) => {
    setFilters(prev => ({
      ...prev,
      [filterType]: value
    }));
  };

  const clearFilters = () => {
    setFilters({
      road: '',
      city: '',
      minDelay: ''
    });
  };

  const formatLastUpdated = () => {
    if (!lastUpdated) return 'Nooit';
    const now = new Date();
    const diffMs = now - lastUpdated;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Zojuist';
    if (diffMins === 1) return '1 minuut geleden';
    return `${diffMins} minuten geleden`;
  };

  const getDelayColor = (delayMinutes) => {
    if (delayMinutes >= 30) return 'bg-red-500';
    if (delayMinutes >= 15) return 'bg-orange-500';
    if (delayMinutes >= 5) return 'bg-yellow-500';
    return 'bg-green-500';
  };

  const getRoadBadgeClasses = (road) => {
    if (road.startsWith('A')) {
      return 'road-badge-a'; // Red background, white text
    } else if (road.startsWith('N')) {
      return 'road-badge-n'; // Yellow background, black text
    }
    return 'road-badge-default';
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-blue-600 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold">🚗 ANWB Verkeersmonitor</h1>
              <p className="text-blue-100 mt-2">Realtime verkeersinformatie uit Nederland</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-blue-100">Laatst bijgewerkt</div>
              <div className="text-lg font-semibold">{formatLastUpdated()}</div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Tabs */}
        <div className="mb-8">
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
                🚦 Verkeersinformatie
              </button>
              <button
                onClick={() => setActiveTab('cameras')}
                className={`py-2 px-1 border-b-2 font-medium text-sm ${
                  activeTab === 'cameras'
                    ? 'border-blue-500 text-blue-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                }`}
              >
                📷 Flitspalen
              </button>
            </nav>
          </div>
        </div>

        {/* Filters */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-xl font-semibold text-gray-900">Filters</h2>
            <div className="flex space-x-3">
              <button
                onClick={clearFilters}
                className="px-4 py-2 text-sm font-medium text-gray-600 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
              >
                Alles Wissen
              </button>
              <button
                onClick={handleRefresh}
                disabled={loading}
                className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {loading ? '🔄 Verversen...' : '🔄 Nu Verversen'}
              </button>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {/* Road Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Weg</label>
              <select
                value={filters.road}
                onChange={(e) => handleFilterChange('road', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Alle Wegen</option>
                {monitoredRoads.map(road => (
                  <option key={road} value={road}>{road}</option>
                ))}
              </select>
            </div>

            {/* City Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Stad</label>
              <select
                value={filters.city}
                onChange={(e) => handleFilterChange('city', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Alle Steden</option>
                {monitoredCities.map(city => (
                  <option key={city} value={city}>{city}</option>
                ))}
              </select>
            </div>

            {/* Delay Filter */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Minimale Vertraging</label>
              <select
                value={filters.minDelay}
                onChange={(e) => handleFilterChange('minDelay', e.target.value)}
                className="w-full border border-gray-300 rounded-md px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="">Elke Vertraging</option>
                {DELAY_FILTERS.map(filter => (
                  <option key={filter.value} value={filter.value}>{filter.label}</option>
                ))}
              </select>
            </div>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-md p-4 mb-8">
            <div className="flex">
              <div className="text-red-400">⚠️</div>
              <div className="ml-3">
                <h3 className="text-sm font-medium text-red-800">Fout</h3>
                <p className="text-sm text-red-700 mt-1">{error}</p>
              </div>
            </div>
          </div>
        )}

        {/* Traffic Jams Tab */}
        {activeTab === 'traffic' && (
          <div>
            {/* Traffic Stats */}
            {trafficData && (
              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
                <div className="bg-white rounded-lg shadow-md p-6">
                  <div className="flex items-center">
                    <div className="p-3 rounded-full bg-blue-100 text-blue-600">
                      🚦
                    </div>
                    <div className="ml-4">
                      <p className="text-sm font-medium text-gray-600">Totaal Files</p>
                      <p className="text-2xl font-semibold text-gray-900">{trafficData.total_jams}</p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow-md p-6">
                  <div className="flex items-center">
                    <div className="p-3 rounded-full bg-yellow-100 text-yellow-600">
                      ⏱️
                    </div>
                    <div className="ml-4">
                      <p className="text-sm font-medium text-gray-600">Gem. Vertraging</p>
                      <p className="text-2xl font-semibold text-gray-900">
                        {trafficData.traffic_jams.length > 0
                          ? Math.round(trafficData.traffic_jams.reduce((sum, jam) => sum + jam.delay_minutes, 0) / trafficData.traffic_jams.length)
                          : 0}
                        <span className="text-sm text-gray-500"> min</span>
                      </p>
                    </div>
                  </div>
                </div>

                <div className="bg-white rounded-lg shadow-md p-6">
                  <div className="flex items-center">
                    <div className="p-3 rounded-full bg-red-100 text-red-600">
                      📏
                    </div>
                    <div className="ml-4">
                      <p className="text-sm font-medium text-gray-600">Totale Lengte</p>
                      <p className="text-2xl font-semibold text-gray-900">
                        {trafficData.traffic_jams.reduce((sum, jam) => sum + jam.length_km, 0).toFixed(1)}
                        <span className="text-sm text-gray-500"> km</span>
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Traffic Jams List */}
            <div className="bg-white rounded-lg shadow-md">
              <div className="px-6 py-4 border-b border-gray-200">
                <h3 className="text-lg font-medium text-gray-900">Verkeersinformatie</h3>
              </div>
              
              {loading && (
                <div className="p-8 text-center">
                  <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
                  <p className="mt-4 text-gray-600">Verkeersinformatie laden...</p>
                </div>
              )}

              {!loading && trafficData && trafficData.traffic_jams.length === 0 && (
                <div className="p-8 text-center">
                  <div className="text-green-500 text-4xl mb-4">✅</div>
                  <h3 className="text-lg font-medium text-gray-900 mb-2">Geen Files</h3>
                  <p className="text-gray-600">Goed nieuws! Geen files gevonden die voldoen aan uw criteria.</p>
                </div>
              )}

              {!loading && trafficData && trafficData.traffic_jams.length > 0 && (
                <div className="divide-y divide-gray-200">
                  {trafficData.traffic_jams.map((jam, index) => (
                    <div key={jam.id || index} className="p-6 hover:bg-gray-50 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3 mb-3">
                            <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-bold ${getRoadBadgeClasses(jam.road)}`}>
                              {jam.road}
                            </span>
                            <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium text-white ${getDelayColor(jam.delay_minutes)}`}>
                              +{jam.delay_minutes} min
                            </span>
                            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-gray-100 text-gray-800">
                              {jam.length_km} km
                            </span>
                          </div>

                          {/* Direction */}
                          {jam.direction && jam.direction !== 'Onbekende richting' && (
                            <p className="text-sm text-blue-600 font-medium mb-1">
                              📍 {jam.direction}
                            </p>
                          )}

                          {/* Location/Route */}
                          {(jam.from_exit && jam.to_exit && jam.from_exit !== 'Onbekend') && (
                            <p className="text-sm text-gray-700 mb-1">
                              🛣️ Van {jam.from_exit} naar {jam.to_exit}
                            </p>
                          )}

                          {/* Cause */}
                          {jam.cause && jam.cause !== 'Onbekende oorzaak' && (
                            <p className="text-sm text-orange-600 mb-1">
                              ⚠️ Oorzaak: {jam.cause}
                            </p>
                          )}
                        </div>
                        <div className="ml-4 text-right">
                          <p className="text-xs text-gray-500">
                            Bijgewerkt: {new Date(jam.last_updated).toLocaleTimeString()}
                          </p>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Speed Cameras Tab */}
        {activeTab === 'cameras' && (
          <div className="bg-white rounded-lg shadow-md">
            <div className="px-6 py-4 border-b border-gray-200">
              <h3 className="text-lg font-medium text-gray-900">Flitspalen</h3>
            </div>
            
            <div className="p-8 text-center">
              <div className="text-blue-500 text-4xl mb-4">🚧</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Flitspalen Binnenkort Beschikbaar</h3>
              <p className="text-gray-600">Flitspaal informatie wordt toegevoegd in een toekomstige update.</p>
            </div>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-8 mt-16">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-300">
            Verkeersinformatie via ANWB • Updates elke 5 minuten • Gemaakt met ❤️ voor veiliger reizen
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;