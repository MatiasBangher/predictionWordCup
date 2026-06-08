import React, { useState, useEffect } from 'react';
import { Calendar, ChevronRight, CheckCircle2 } from 'lucide-react';

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const MatchdayPredictions = () => {
  const [predictions, setPredictions] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchPredictions();
  }, []);

  const fetchPredictions = async () => {
    try {
      setLoading(true);
      // Fetch predictions for Matchday 1
      const res = await fetch(`${API_URL}/api/matchday-predictions?matchday=1`);
      const json = await res.json();
      setPredictions(json.data || []);
    } catch (error) {
      console.error("Error fetching matchday predictions:", error);
    } finally {
      setLoading(false);
    }
  };

  // Helper to map country names to 2-letter ISO codes for flagcdn
  const getCountryCode = (countryName) => {
    const map = {
      // Grupo A
      "México": "mx", "Sudáfrica": "za", "Corea del Sur": "kr", "República Checa": "cz",
      // Grupo B
      "Canadá": "ca", "Bosnia y Herzegovina": "ba", "Qatar": "qa", "Suiza": "ch",
      // Grupo C
      "Brasil": "br", "Marruecos": "ma", "Haití": "ht", "Escocia": "gb-sct",
      // Grupo D
      "Estados Unidos": "us", "Paraguay": "py", "Australia": "au", "Turquía": "tr",
      // Grupo E
      "Alemania": "de", "Curaçao": "cw", "Costa de Marfil": "ci", "Ecuador": "ec",
      // Grupo F
      "Países Bajos": "nl", "Japón": "jp", "Suecia": "se", "Túnez": "tn",
      // Grupo G
      "Irán": "ir", "Nueva Zelanda": "nz", "Bélgica": "be", "Egipto": "eg",
      // Grupo H
      "Arabia Saudita": "sa", "Uruguay": "uy", "España": "es", "Cabo Verde": "cv",
      // Grupo I
      "Francia": "fr", "Senegal": "sn", "Irak": "iq", "Noruega": "no",
      // Grupo J
      "Argentina": "ar", "Argelia": "dz", "Austria": "at", "Jordania": "jo",
      // Grupo K
      "Portugal": "pt", "Congo RD": "cd", "Uzbekistán": "uz", "Colombia": "co",
      // Grupo L
      "Ghana": "gh", "Panamá": "pa", "Inglaterra": "gb-eng", "Croacia": "hr",
    };
    return map[countryName] || "xx";
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full text-slate-400">
        <div className="animate-pulse flex flex-col items-center">
          <div className="w-12 h-12 border-4 border-emerald-500/30 border-t-emerald-500 rounded-full animate-spin mb-4"></div>
          <p>Analizando modelos predictivos...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-3xl mx-auto pb-12">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-white mb-2">Porcentajes y Predicciones</h1>
        <p className="text-slate-400">Mi predicción en cada encuentro y un breve análisis basado en Machine Learning (XGBoost).</p>
      </div>

      <div className="flex items-center mb-6">
        <h2 className="text-xl font-semibold text-emerald-400 flex items-center">
          Ya está lista la Jornada 1
          <ChevronRight className="w-5 h-5 ml-1" />
        </h2>
      </div>

      <div className="space-y-6">
        {predictions.map((match, index) => {
          const homeCode = getCountryCode(match.home_team);
          const awayCode = getCountryCode(match.away_team);
          const dateObj = new Date(match.date);
          const dateStr = dateObj.toLocaleDateString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
          const timeStr = dateObj.toLocaleTimeString('es-ES', { hour: '2-digit', minute: '2-digit' });
          
          return (
            <div key={index} className="mb-10">
              <h3 className="text-white font-medium mb-3 capitalize">{dateStr}</h3>
              
              <div className="bg-[#1a1b26] rounded-2xl border border-slate-800 overflow-hidden shadow-2xl">
                {/* Header */}
                <div className="flex justify-between items-center px-5 py-4 border-b border-slate-800/50 text-sm">
                  <div className="flex items-center space-x-3">
                    <span className="bg-emerald-500/20 text-emerald-400 px-3 py-1 rounded-full text-xs font-semibold">
                      {match.group}
                    </span>
                    <span className="text-slate-300">Jornada 1</span>
                  </div>
                  <div className="text-slate-400 flex items-center">
                    {dateObj.getDate()} de {dateObj.toLocaleDateString('es-ES', {month: 'long'})} · {timeStr}h
                  </div>
                </div>

                {/* Teams Layout */}
                <div className="px-6 py-8 relative">
                  <div className="flex justify-between items-center">
                    {/* Home Team */}
                    <div className="flex flex-col items-center w-1/3">
                      <div className="w-20 h-14 mb-3 overflow-hidden rounded-md shadow-[0_0_15px_rgba(0,0,0,0.5)]">
                        <img 
                          src={`https://flagcdn.com/w160/${homeCode}.png`} 
                          alt={match.home_team}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <span className="text-lg font-semibold text-white">{match.home_team}</span>
                    </div>

                    {/* VS & Stadium */}
                    <div className="flex flex-col items-center w-1/3 text-center">
                      <span className="text-3xl font-black text-indigo-500 mb-2 italic">VS</span>
                      <span className="text-xs text-slate-500">{match.stadium}</span>
                    </div>

                    {/* Away Team */}
                    <div className="flex flex-col items-center w-1/3">
                      <div className="w-20 h-14 mb-3 overflow-hidden rounded-md shadow-[0_0_15px_rgba(0,0,0,0.5)]">
                        <img 
                          src={`https://flagcdn.com/w160/${awayCode}.png`} 
                          alt={match.away_team}
                          className="w-full h-full object-cover"
                        />
                      </div>
                      <span className="text-lg font-semibold text-white">{match.away_team}</span>
                    </div>
                  </div>
                </div>

                {/* Probabilities */}
                <div className="px-6 pb-6">
                  <h4 className="text-xs font-semibold text-slate-500 mb-3 tracking-wider uppercase">Probabilidades</h4>
                  
                  {/* Progress Bar */}
                  <div className="h-3 w-full bg-slate-800 rounded-full overflow-hidden flex mb-3 shadow-inner">
                    <div style={{ width: `${match.probabilities.home_win}%` }} className="bg-indigo-500 h-full"></div>
                    <div style={{ width: `${match.probabilities.draw}%` }} className="bg-cyan-500 h-full"></div>
                    <div style={{ width: `${match.probabilities.away_win}%` }} className="bg-amber-500 h-full"></div>
                  </div>
                  
                  {/* Legends */}
                  <div className="flex justify-between text-sm">
                    <div className="flex items-center">
                      <div className="w-2 h-2 rounded-full bg-indigo-500 mr-2"></div>
                      <span className="text-slate-300">{match.home_team} <span className="font-bold text-white">{match.probabilities.home_win}%</span></span>
                    </div>
                    <div className="flex items-center">
                      <div className="w-2 h-2 rounded-full bg-cyan-500 mr-2"></div>
                      <span className="text-slate-300">Empate <span className="font-bold text-cyan-400">{match.probabilities.draw}%</span></span>
                    </div>
                    <div className="flex items-center">
                      <span className="text-slate-300"><span className="font-bold text-amber-400">{match.probabilities.away_win}%</span> {match.away_team}</span>
                      <div className="w-2 h-2 rounded-full bg-amber-500 ml-2"></div>
                    </div>
                  </div>
                </div>

                {/* Analyst Card */}
                <div className="px-6 pb-6">
                  <div className="border border-indigo-500/30 rounded-xl p-4 bg-indigo-900/10 mb-4">
                    <div className="text-xs text-slate-400 uppercase tracking-wider mb-2">Predicción del Analista</div>
                    <div className="flex justify-between items-center">
                      <span className="text-2xl font-bold text-white">{match.prediction.winner}</span>
                      <span className={`px-3 py-1 rounded-full text-sm font-medium flex items-center ${match.prediction.confidence === 'Confianza Alta' ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30' : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'}`}>
                        <div className={`w-2 h-2 rounded-full mr-2 ${match.prediction.confidence === 'Confianza Alta' ? 'bg-emerald-400' : 'bg-amber-400'}`}></div>
                        {match.prediction.confidence}
                      </span>
                    </div>
                  </div>
                  
                  {/* Analysis Text */}
                  <p className="text-slate-400 text-sm leading-relaxed">
                    {match.prediction.analysis}
                  </p>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};

export default MatchdayPredictions;
