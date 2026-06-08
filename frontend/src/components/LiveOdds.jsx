import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { Link } from 'react-router-dom';
import { RefreshCw, ExternalLink, ChevronDown, ChevronUp, AlertCircle, Percent, Target } from 'lucide-react';

export default function LiveOdds() {
  const [matches, setMatches] = useState([]);
  const [loading, setLoading] = useState(true);
  const [expandedMatch, setExpandedMatch] = useState(null);

  const fetchOdds = async () => {
    setLoading(true);
    try {
      const response = await axios.get('http://127.0.0.1:8000/api/live-odds');
      // The new API returns { data: [ { match... }, { match... } ] }
      setMatches(response.data.data || []);
    } catch (error) {
      console.error("Error fetching live odds:", error);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchOdds();
  }, []);

  const toggleMatch = (id) => {
    if (expandedMatch === id) {
      setExpandedMatch(null);
    } else {
      setExpandedMatch(id);
    }
  };

  const formatMarketLabel = (market) => {
    switch (market) {
      case 'h2h': return 'Ganador del Partido';
      case 'h2h_lay': return 'Doble Oportunidad (Lay)';
      case 'totals': 
      case 'alternate_totals': return 'Goles Totales';
      case 'spreads': 
      case 'alternate_spreads': return 'Handicap / Doble Oportunidad';
      case 'btts': return 'Ambos Equipos Anotan';
      case 'draw_no_bet': return 'Empate Anula Apuesta';
      case 'team_corners': return 'Córners del Equipo';
      case 'player_shots_on_target':
      case 'Player Shots on Target': return 'Tiros al Arco (Jugador)';
      case 'Corners Over/Under': return 'Córners Totales';
      case 'Total Cards': return 'Tarjetas Totales';
      case 'Home Team Total Goals': return 'Goles Totales (Local)';
      case 'Corners 1st Half': return 'Córners 1er Tiempo';
      default: return market.replace(/_/g, ' ');
    }
  };

  const formatSelectionLabel = (market, selection) => {
    if (market === 'h2h') return `Victoria de ${selection}`;
    if (market === 'h2h_lay') return `No gana ${selection} (Empate o Derrota)`;
    if (market === 'totals' || market === 'alternate_totals') {
      if (selection.startsWith('Over')) return selection.replace('Over', 'Más de (Over)');
      if (selection.startsWith('Under')) return selection.replace('Under', 'Menos de (Under)');
    }
    if (market === 'btts') {
      if (selection === 'Yes') return 'Sí';
      if (selection === 'No') return 'No';
    }
    if (market === 'draw_no_bet') {
      return `Victoria de ${selection} (DNB)`;
    }
    if (market === 'spreads' || market === 'alternate_spreads') {
      // Parse team and spread value, e.g., "Mexico 0.5" or "Czech Republic -1.5"
      const match = selection.match(/^(.*?)\s+([\+\-]?\d+(\.\d+)?)$/);
      if (match) {
        const team = match[1];
        const point = parseFloat(match[2]);
        if (point === 0.5) return `Victoria o Empate de ${team}`;
        if (point === 0.0) return `Victoria de ${team} (Empate Anula Apuesta)`;
        if (point === -0.5) return `Victoria de ${team} (Hándicap -0.5)`;
        if (point > 0) return `${team} +${point} (Gana o pierde por menos de ${Math.ceil(point)})`;
        if (point < 0) return `${team} ${point} (Debe ganar por más de ${Math.abs(Math.floor(point))})`;
      }
      return selection;
    }
    return selection;
  };

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
        <div>
          <h2 className="text-3xl font-bold text-slate-100">Fase de Grupos: Fijinis</h2>
          <p className="text-slate-400">Encuentra las apuestas más seguras por partido (Cuotas 1.1 - 1.5)</p>
        </div>
        <button 
          onClick={fetchOdds}
          disabled={loading}
          className="flex items-center px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg transition-colors border border-slate-700 w-fit"
        >
          <RefreshCw className={`w-4 h-4 mr-2 ${loading ? 'animate-spin' : ''}`} />
          {loading ? 'Actualizando...' : 'Actualizar Cuotas'}
        </button>
      </header>

      <div className="space-y-4">
        {matches.map((match) => (
          <div key={match.external_match_id} className="glass-panel border border-slate-700/50 overflow-hidden rounded-xl">
            {/* Match Header (Clickable) */}
            <div 
              className="p-5 flex flex-col md:flex-row md:items-center justify-between cursor-pointer hover:bg-slate-800/30 transition-colors"
              onClick={() => toggleMatch(match.external_match_id)}
            >
              <div className="flex flex-col mb-4 md:mb-0">
                <span className="text-xs font-semibold text-emerald-400 uppercase tracking-wider mb-1">{match.group}</span>
                <div className="flex items-center text-xl font-bold text-slate-100">
                  <span className="w-32 md:w-40 text-right">{match.home_team}</span>
                  <span className="px-4 text-slate-500 text-sm">VS</span>
                  <span className="w-32 md:w-40">{match.away_team}</span>
                </div>
                <div className="text-sm text-slate-400 mt-1">
                  {new Date(match.commence_time).toLocaleString('es-ES', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute:'2-digit' })}
                </div>
              </div>

              <div className="flex items-center gap-4">
                <div className="bg-slate-800/80 px-3 py-1.5 rounded-lg border border-slate-700">
                  <span className="text-sm font-medium text-slate-300">
                    <span className="text-emerald-400 font-bold">{match.fijinis?.length || 0}</span> Fijinis encontradas
                  </span>
                </div>
                {expandedMatch === match.external_match_id ? (
                  <ChevronUp className="w-5 h-5 text-slate-400" />
                ) : (
                  <ChevronDown className="w-5 h-5 text-slate-400" />
                )}
              </div>
            </div>

            {/* Match Details (Expanded) */}
            {expandedMatch === match.external_match_id && (
              <div className="border-t border-slate-700/50 bg-slate-900/50 p-5">
                
                <div className="mb-4 flex justify-between items-center">
                  <h4 className="font-semibold text-slate-200">Mercados de Alta Confianza detectados:</h4>
                  <Link to="/analysis" className="text-sm text-blue-400 hover:text-blue-300 flex items-center transition-colors">
                    Ver Análisis de Equipos <ExternalLink className="w-4 h-4 ml-1" />
                  </Link>
                </div>

                <div className="grid grid-cols-1 gap-4">
                  {match.fijinis?.map((fijini, index) => (
                    <div key={index} className="bg-slate-800/40 rounded-lg p-4 border border-slate-700/50">
                      
                      <div className="flex flex-col md:flex-row md:items-start justify-between mb-3 gap-4">
                        {/* Prop Info */}
                        <div className="flex-1">
                          <div className="flex items-center mb-1">
                            <Target className="w-4 h-4 text-emerald-400 mr-2" />
                            <span className="text-sm text-slate-400 uppercase font-semibold tracking-wide">
                              {formatMarketLabel(fijini.market)}
                            </span>
                          </div>
                          <p className="text-lg font-bold text-slate-100">{formatSelectionLabel(fijini.market, fijini.selection)}</p>
                        </div>

                        {/* Odds & Prob */}
                        <div className="flex items-center gap-6 bg-slate-900/80 p-3 rounded-lg border border-slate-700">
                          <div className="text-center">
                            <p className="text-xs text-slate-400 mb-1 uppercase">Cuota 1xBet</p>
                            <p className="text-xl font-bold text-slate-100">x{fijini.price.toFixed(2)}</p>
                          </div>
                          <div className="w-px h-10 bg-slate-700"></div>
                          <div className="text-center">
                            <p className="text-xs text-slate-400 mb-1 uppercase">Prob. Real</p>
                            <p className="text-xl font-bold text-emerald-400 flex items-center">
                              {fijini.analysis.actual_probability}% <Percent className="w-4 h-4 ml-0.5" />
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* Text Analysis from AI */}
                      <div className="mt-3 bg-slate-900/50 rounded p-3 text-sm text-slate-300 flex items-start border-l-2 border-emerald-500">
                        <AlertCircle className="w-4 h-4 text-emerald-500 mr-2 flex-shrink-0 mt-0.5" />
                        <p className="leading-relaxed">
                          <strong className="text-slate-200">Análisis del Modelo: </strong>
                          {fijini.analysis.text}
                        </p>
                      </div>

                    </div>
                  ))}
                </div>

              </div>
            )}
          </div>
        ))}

        {matches.length === 0 && !loading && (
          <div className="text-center p-12 glass-panel">
            <p className="text-slate-400">No hay partidos disponibles con cuotas fijinis en este momento.</p>
          </div>
        )}
      </div>
    </div>
  );
}
