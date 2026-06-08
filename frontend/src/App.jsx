import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import { Activity, TrendingUp, ShieldAlert, BarChart3, Calendar } from 'lucide-react';
import Dashboard from './components/Dashboard';
import LiveOdds from './components/LiveOdds';
import TeamProfile from './components/TeamProfile';
import MatchdayPredictions from './components/MatchdayPredictions';

function App() {
  return (
    <Router>
      <div className="min-h-screen flex flex-col md:flex-row font-sans">
        {/* Sidebar */}
        <aside className="w-full md:w-64 glass-panel md:m-4 flex flex-col justify-between">
          <div>
            <div className="p-6">
              <h1 className="text-2xl font-bold text-transparent bg-clip-text bg-gradient-to-r from-emerald-400 to-cyan-400">
                Fijinis WC '26
              </h1>
              <p className="text-slate-400 text-sm mt-1">Smart Betting Tracker</p>
            </div>
            
            <nav className="mt-6">
              <Link to="/" className="flex items-center px-6 py-3 text-slate-300 hover:bg-slate-800/50 hover:text-emerald-400 transition-colors border-l-2 border-transparent hover:border-emerald-400">
                <BarChart3 className="w-5 h-5 mr-3" />
                Dashboard (Paper Trading)
              </Link>
              <Link to="/live" className="flex items-center px-6 py-3 text-slate-300 hover:bg-slate-800/50 hover:text-emerald-400 transition-colors border-l-2 border-transparent hover:border-emerald-400">
                <Activity className="w-5 h-5 mr-3" />
                Cuotas en Vivo
              </Link>
              <Link to="/analysis" className="flex items-center px-6 py-3 text-slate-300 hover:bg-slate-800/50 hover:text-emerald-400 transition-colors border-l-2 border-transparent hover:border-emerald-400">
                <ShieldAlert className="w-5 h-5 mr-3" />
                Análisis de Equipos
              </Link>
              <Link to="/predictions" className="flex items-center px-6 py-3 text-slate-300 hover:bg-slate-800/50 hover:text-emerald-400 transition-colors border-l-2 border-transparent hover:border-emerald-400">
                <Calendar className="w-5 h-5 mr-3" />
                Predicciones (Jornadas)
              </Link>
            </nav>
          </div>
          
          <div className="p-6">
            <div className="bg-slate-800/50 p-4 rounded-xl border border-slate-700/50">
              <div className="flex items-center text-sm text-slate-300 mb-2">
                <TrendingUp className="w-4 h-4 mr-2 text-emerald-400" />
                Rendimiento Modelo
              </div>
              <div className="text-2xl font-bold text-emerald-400">+14.2%</div>
            </div>
          </div>
        </aside>

        {/* Main Content */}
        <main className="flex-1 p-4 md:p-8 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/live" element={<LiveOdds />} />
            <Route path="/analysis" element={<TeamProfile />} />
            <Route path="/predictions" element={<MatchdayPredictions />} />
          </Routes>
        </main>
      </div>
    </Router>
  );
}

export default App;
