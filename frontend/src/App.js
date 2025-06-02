import React, { useState, useEffect } from 'react';
import './App.css';
import axios from 'axios';

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

function App() {
  const [trafficData, setTrafficData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [minDelay, setMinDelay] = useState('');
  const [lastUpdated, setLastUpdated] = useState(null);
  const [refreshing, setRefreshing] = useState(false);

  const TARGET_ROADS = ["A2", "A16", "A50", "A58", "A59", "A65", "A67", "A73", "A76", "A270", "N2", "N69", "N266", "N270", "N279"];
  const TARGET_CITIES = [
    // Original cities
    "Eindhoven", "Venlo", "Weert", "'s-Hertogenbosch", "Roermond", "Maasbracht",
    "Nijmegen", "Oss", "Zonzeel", "Breda", "Tilburg", "Rotterdam", "Deurne",
    "Helmond", "Venray", "Heerlen", "Maastricht", "Belgische Grens", "Duitse Grens", 
    "Valkenswaard", "Moerdijkbrug", "Culemborg",
    
    // A2 exits (Utrecht – 's-Hertogenbosch – Eindhoven – Maastricht)
    "Utrecht-Centrum", "Nieuwegein", "Nieuwegein-Zuid", "Vianen", "Everdingen", 
    "Beesd", "Geldermalsen", "Waardenburg", "Zaltbommel", "Kerkdriel", "Rosmalen",
    "Veghel", "St. Michielsgestel", "Vught", "'s-Hertogenbosch-Centrum", "Boxtel-Noord", 
    "Boxtel", "Best-West", "Best", "Eindhoven-Airport", "Eindhoven-Centrum", 
    "Meerhoven-Zuid", "Veldhoven", "Veldhoven-Zuid", "High Tech Campus", "Waalre",
    "Leende", "Maarheeze", "Budel", "Weert-Noord", "Nederweert", "Kelpen-Oler",
    "Grathem", "Wessem", "St. Joost", "Echt", "Roosteren", "Born", "Urmond",
    "Elsloo", "Ulestraten", "Meerssen", "Maastricht-Noord", "Maastricht-Centrum Noord",
    "Maastricht-Centrum Zuid", "Maastricht-Zuid", "Gronsveld", "Oost-Maarland", "Eijsden",
    
    // A16 exits (Belgische Grens – Breda – Rotterdam)
    "Rotterdam-Prins Alexander", "Rotterdam-Kralingen", "Capelle aan den IJssel",
    "Rotterdam-Feijenoord", "Hendrik-Ido-Ambacht", "Zwijndrecht", "Dordrecht-Centrum",
    "Dordrecht", "Dordrecht-Willemsdorp", "Zevenbergschen Hoek", "Breda-Noord",
    "Breda-West", "Princeville", "Industrie Breda 6000-7000",
    
    // A50 exits (Eindhoven – Oss – Arnhem)
    "Industrie Ekkersrijt", "Son en Breugel", "St. Oedenrode", "Eerde", "Veghel-Noord",
    "Volkel", "Zeeland", "Nistelrode", "Ravenstein", "Valburg", "Heteren", "Renkum", "Arnhem",
    
    // A58 exits (Eindhoven – Tilburg – Breda)
    "Oirschot", "Moergestel", "Tilburg-Centrum-Oost", "Tilburg-Centrum-West",
    "Tilburg-Reeshof", "Bavel", "Ulvenhout",
    
    // A59 exits (Zonzeel – 's-Hertogenbosch – Oss)
    "Terheijden", "Made", "Oosterhout", "Raamsdonksveer", "Waspik", "Sprang-Capelle-West",
    "Waalwijk", "Waalwijk-Centrum", "Waalwijk-Oost", "Drunen-West", "Heusden", 
    "Nieuwkuijk", "Vlijmen", "Ring 's-Hertogenbosch-West", "Engelen", 
    "'s-Hertogenbosch-Maaspoort", "Rosmalen-Oost", "Kruisstraat", "Nuland", "Oss-Oost",
    
    // A65 exits ('s-Hertogenbosch – Tilburg)
    "Vught-Centrum", "Vught-Zuid", "Helvoirt", "Haaren", "Biezenmortel", "Udenhout",
    "Berkel-Enschot", "Tilburg-Noord",
    
    // A67 exits (Belgische Grens – Eindhoven – Venlo – Duitse Grens)
    "Hapert", "Eersel", "Geldrop", "Someren", "Asten", "Liessel", "Panningen",
    "Venlo-Noordwest", "Noorderbrug", "Velden",
    
    // A73 exits (Nijmegen – Maasbracht)
    "Beuningen", "Wijchen", "Nijmegen-Dukenburg", "Malden", "Cuijk", "Haps",
    "Boxmeer", "Vierlingsbeek", "Venray-Noord", "Horst-Noord", "Horst", "Grubbenvorst",
    "Venlo-West", "Maasbree", "Blerick", "Zuiderbrug", "Venlo-Zuid", "Belfeld",
    "Beesel", "Roermond", "Roermond-Oost", "Linne",
    
    // A76 exits (Belgische Grens – Geleen – Heerlen – Duitse Grens)
    "Stein", "Geleen", "Spaubeek", "Nuth", "Heerlen-Noord", "Simpelveld",
    
    // Junctions (Knooppunten)
    "Knp. Oudenrijn", "Knp. Everdingen", "Knp. Deil", "Knp. Empel", "Knp. Hintham",
    "Knp. Ekkersweijer", "Knp. Batadorp", "Knp. De Hogt", "Knp. Leenderheide",
    "Knp. Het Vonderen", "Knp. Kerensheide", "Knp. Kruisdonk", "Knp. Terbregseplein",
    "Knp. Ridderkerk", "Knp. Klaverpolder", "Knp. Galder", "Knp. Paalgraven",
    "Knp. Bankhoef", "Knp. Ewijk", "Knp. Grijsoord", "Knp. De Baars", "Knp. St. Annabosch",
    "Knp. Hooipolder", "Knp. Vught", "Knp. Zaarderheiken", "Knp. Neerbosch",
    "Knp. Rijkevoort", "Knp. Tiglia", "Knp. Ten Esschen", "Knp. Kunderberg",
    
    // Bridges and Tunnels
    "Van Brienenoordbrug", "Drechttunnel", "Tacitusbrug", "Swalmentunnel", "Roertunnel"
  ];

  const DELAY_OPTIONS = [
    { value: 1, label: '1+ minuten' },
    { value: 5, label: '5+ minuten' },
    { value: 10, label: '10+ minuten' },
    { value: 15, label: '15+ minuten' },
    { value: 20, label: '20+ minuten' },
    { value: 25, label: '25+ minuten' },
    { value: 30, label: '30+ minuten' }
  ];

  const fetchTrafficData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const params = new URLSearchParams();
      
      // Apply all road and city filters by default
      params.append('roads', TARGET_ROADS.join(','));
      params.append('cities', TARGET_CITIES.join(','));
      
      // Only apply delay filter if selected
      if (minDelay) {
        params.append('min_delay', minDelay);
      }

      const response = await axios.get(`${API}/traffic?${params.toString()}`);
      setTrafficData(response.data);
      setLastUpdated(new Date(response.data.last_updated));
    } catch (err) {
      setError('Fout bij het ophalen van verkeersgegevens');
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
      setError('Fout bij het vernieuwen van gegevens');
      console.error('Error refreshing data:', err);
    } finally {
      setRefreshing(false);
    }
  };

  const handleDelayFilter = (delay) => {
    setMinDelay(prev => prev === delay ? '' : delay);
  };

  const formatTimeAgo = (timestamp) => {
    if (!timestamp) return 'Onbekend';
    const diff = Math.floor((new Date() - timestamp) / 1000);
    if (diff < 60) return `${diff} seconden geleden`;
    if (diff < 3600) return `${Math.floor(diff / 60)} minuten geleden`;
    return `${Math.floor(diff / 3600)} uur geleden`;
  };

  const getDelayColor = (delayMinutes) => {
    if (delayMinutes >= 30) return 'text-red-600 bg-red-50';
    if (delayMinutes >= 15) return 'text-orange-600 bg-orange-50';
    if (delayMinutes >= 5) return 'text-yellow-600 bg-yellow-50';
    return 'text-green-600 bg-green-50';
  };

  const getRoadStyle = (road) => {
    if (road.startsWith('A')) {
      return 'bg-red-600 text-white';
    } else if (road.startsWith('N')) {
      return 'bg-yellow-400 text-black';
    }
    return 'bg-blue-100 text-blue-800'; // fallback
  };

  useEffect(() => {
    fetchTrafficData();
  }, [minDelay]);

  useEffect(() => {
    // Auto-refresh every 5 minutes
    const interval = setInterval(fetchTrafficData, 5 * 60 * 1000);
    return () => clearInterval(interval);
  }, [minDelay]);

  if (loading && !trafficData) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Verkeersgegevens laden...</p>
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
              <h1 className="text-2xl font-bold text-gray-900">Glow FM Verkeer</h1>
              <p className="text-sm text-gray-600">
                Live files en flitsers in Nederland
              </p>
            </div>
            <div className="flex items-center space-x-4">
              <div className="text-sm text-gray-500">
                Laatst bijgewerkt: {formatTimeAgo(lastUpdated)}
              </div>
              <button
                onClick={refreshData}
                disabled={refreshing}
                className="bg-blue-600 hover:bg-blue-700 disabled:bg-blue-400 text-white px-4 py-2 rounded-lg text-sm font-medium transition-colors"
              >
                {refreshing ? 'Vernieuwen...' : 'Vernieuwen'}
              </button>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {/* Stats */}
        {trafficData && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-gray-900">{trafficData.filtered_jams}</div>
              <div className="text-sm text-gray-600">Files</div>
              {trafficData.total_jams !== trafficData.filtered_jams && (
                <div className="text-xs text-gray-500">
                  van {trafficData.total_jams} totaal
                </div>
              )}
            </div>
            <div className="bg-white rounded-lg shadow p-6">
              <div className="text-2xl font-bold text-gray-900">{trafficData.speed_cameras.length}</div>
              <div className="text-sm text-gray-600">Flitsers</div>
            </div>
          </div>
        )}

        {/* Delay Filter Only */}
        <div className="bg-white rounded-lg shadow mb-8">
          <div className="p-6">
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Filter op Vertraging</h2>
            
            <div className="flex flex-wrap gap-2">
              {DELAY_OPTIONS.map(option => (
                <button
                  key={option.value}
                  onClick={() => handleDelayFilter(option.value)}
                  className={`px-3 py-1 rounded-full text-sm font-medium transition-colors ${
                    minDelay === option.value
                      ? 'bg-red-600 text-white'
                      : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            
            <div className="mt-4 text-sm text-gray-600">
              <p><strong>Automatisch gefilterd op:</strong></p>
              <p>• Wegen: {TARGET_ROADS.join(', ')}</p>
              <p>• Steden: {TARGET_CITIES.slice(0, 5).join(', ')} en {TARGET_CITIES.length - 5} meer</p>
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
                <h2 className="text-lg font-semibold text-gray-900">Files</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {trafficData.traffic_jams.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    Geen files, door naar de hits!
                  </div>
                ) : (
                  trafficData.traffic_jams.map((jam, index) => (
                    <div key={jam.id || index} className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <div className="flex items-center space-x-3">
                            <span className={`text-xs font-semibold px-2.5 py-0.5 rounded ${getRoadStyle(jam.road)}`}>
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
                <h2 className="text-lg font-semibold text-gray-900">Flitsers</h2>
              </div>
              <div className="divide-y divide-gray-200">
                {trafficData.speed_cameras.length === 0 ? (
                  <div className="p-6 text-center text-gray-500">
                    Geen flitsers, door naar de hits!
                  </div>
                ) : (
                  trafficData.speed_cameras.map((camera, index) => (
                    <div key={camera.id || index} className="p-6">
                      <div className="flex items-start space-x-3">
                        <span className={`text-xs font-semibold px-2.5 py-0.5 rounded ${getRoadStyle(camera.road)}`}>
                          {camera.road}
                        </span>
                        {camera.hectometer && (
                          <span className="bg-green-600 text-white text-xs font-semibold px-2.5 py-0.5 rounded">
                            km {camera.hectometer}
                          </span>
                        )}
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
