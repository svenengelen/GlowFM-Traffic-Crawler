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
    road: '', // All roads by default
    city: '', // All cities by default  
    minDelay: ''
  });
  const [lastUpdated, setLastUpdated] = useState(null);

  const backendUrl = process.env.REACT_APP_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL;

  // Fetch traffic data when filters change
  useEffect(() => {
    fetchTrafficData();
  }, [filters]);

  // Auto-refresh every 5 minutes
  useEffect(() => {
    const interval = setInterval(fetchTrafficData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [filters]);

  const fetchTrafficData = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      // Always use all roads and cities - no filtering by road/city
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
              <h1 className="text-3xl font-bold">📻 Glow FM Verkeer</h1>
              <p className="text-blue-100 mt-2">Staan er files rondom Eindhoven?</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-blue-100">Laatst bijgewerkt</div>
              <div className="text-lg font-semibold">{formatLastUpdated()}</div>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
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

          <div className="grid grid-cols-1 md:grid-cols-1 gap-4">
            {/* Only Delay Filter */}
            <div className="max-w-md">
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
                <div className="p-3 rounded-full bg-green-100 text-green-600">
                  🛣️
                </div>
                <div className="ml-4">
                  <p className="text-sm font-medium text-gray-600">Mobiele Flitsers</p>
                  <p className="text-2xl font-semibold text-gray-900">
                    {trafficData.speed_cameras.filter(cam => cam.flitser_type === 'Mobiele flitser').length}
                  </p>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Files Section */}
        <div className="bg-white rounded-lg shadow-md mb-8">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">🚦 Files</h3>
          </div>
          
          {loading && (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Files laden...</p>
            </div>
          )}

          {!loading && trafficData && trafficData.traffic_jams.length === 0 && (
            <div className="p-8 text-center">
              <div className="text-green-500 text-4xl mb-4">✅</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Geen Files</h3>
              <p className="text-gray-600">Goed nieuws! Geen files gevonden rondom Eindhoven.</p>
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

                      {/* Direction and Locations */}
                      {jam.direction && jam.direction !== 'Onbekende richting' && (
                        <p className="text-sm text-blue-600 font-medium mb-1">
                          📍 {jam.direction}
                        </p>
                      )}

                      {/* Route Details */}
                      {jam.route_details && jam.route_details !== 'Route onbekend' && (
                        <p className="text-sm text-gray-700 mb-1">
                          🛣️ {jam.route_details}
                        </p>
                      )}

                      {/* Source and Destination */}
                      {(jam.source_location && jam.destination_location && 
                        jam.source_location !== 'Onbekend' && jam.destination_location !== 'Onbekend') && (
                        <p className="text-sm text-gray-600 mb-1">
                          📍 Van {jam.source_location} naar {jam.destination_location}
                        </p>
                      )}

                      {/* Detailed Cause */}
                      {jam.cause && jam.cause !== 'Oorzaak onbekend' && (
                        <p className="text-sm text-orange-600 mb-1 italic">
                          ⚠️ {jam.cause}
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

        {/* Flitsers Section */}
        <div className="bg-white rounded-lg shadow-md">
          <div className="px-6 py-4 border-b border-gray-200">
            <h3 className="text-lg font-medium text-gray-900">📷 Flitsers</h3>
          </div>
          
          {loading && (
            <div className="p-8 text-center">
              <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
              <p className="mt-4 text-gray-600">Flitser informatie laden...</p>
            </div>
          )}

          {!loading && trafficData && trafficData.speed_cameras.length === 0 && (
            <div className="p-8 text-center">
              <div className="text-blue-500 text-4xl mb-4">📷</div>
              <h3 className="text-lg font-medium text-gray-900 mb-2">Geen Flitsers</h3>
              <p className="text-gray-600">Geen actieve flitsers gevonden rondom Eindhoven.</p>
            </div>
          )}

          {!loading && trafficData && trafficData.speed_cameras.length > 0 && (
            <div className="divide-y divide-gray-200">
              {trafficData.speed_cameras.map((camera, index) => (
                <div key={camera.id || index} className="p-6 hover:bg-gray-50 transition-colors">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <div className="flex items-center space-x-3 mb-3">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-bold ${getRoadBadgeClasses(camera.road)}`}>
                          {camera.road}
                        </span>
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${
                          camera.is_active ? 'bg-green-100 text-green-800' : 'bg-gray-100 text-gray-800'
                        }`}>
                          {camera.flitser_type}
                        </span>
                        {camera.is_active && (
                          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-800">
                            ACTIEF
                          </span>
                        )}
                      </div>

                      {/* Location */}
                      {camera.location && camera.location !== 'Locatie onbekend' && (
                        <p className="text-sm text-gray-700 mb-1">
                          📍 {camera.location}
                        </p>
                      )}

                      {/* Direction */}
                      {camera.direction && camera.direction !== 'Onbekende richting' && (
                        <p className="text-sm text-blue-600 mb-1">
                          🧭 {camera.direction}
                        </p>
                      )}

                      {/* Flitser Type Details */}
                      <div className="flex items-center space-x-4 mt-2">
                        {camera.flitser_type === 'Mobiele flitser' && (
                          <span className="text-xs text-gray-500">🚐 Mobiele snelheidscontrole</span>
                        )}
                        {camera.flitser_type === 'Actieve flitser' && (
                          <span className="text-xs text-gray-500">📷 Actieve flitspaal</span>
                        )}
                        {camera.flitser_type === 'Snelheidscontrole' && (
                          <span className="text-xs text-gray-500">🚨 Dynamische snelheidscontrole</span>
                        )}
                        {camera.is_active && (
                          <span className="text-xs text-green-600 font-medium">🟢 Momenteel actief</span>
                        )}
                      </div>
                    </div>
                    <div className="ml-4 text-right">
                      <p className="text-xs text-gray-500">
                        Bijgewerkt: {new Date(camera.last_updated).toLocaleTimeString()}
                      </p>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Footer */}
      <footer className="bg-gray-800 text-white py-8 mt-16">
        <div className="max-w-7xl mx-auto px-4 text-center">
          <p className="text-gray-300">
            Verkeersinfo vanuit de ANWB. Problemen? Contact team techniek!
          </p>
        </div>
      </footer>
    </div>
  );
}

export default App;