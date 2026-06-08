import React from 'react';
import { ShieldAlert, TrendingUp, Users, AlertTriangle } from 'lucide-react';

export default function TeamProfile() {
  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="mb-8">
        <h2 className="text-3xl font-bold text-slate-100">Análisis del Partido</h2>
        <p className="text-slate-400">Datos detallados y proyecciones</p>
      </header>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Home Team */}
        <div className="glass-panel p-6 border-t-4 border-t-emerald-500">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-2xl font-bold text-slate-100">Argentina</h3>
              <p className="text-emerald-400 font-medium mt-1">Forma: W W W W W</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-slate-400">Probabilidad de Victoria</div>
              <div className="text-2xl font-bold text-emerald-400">78%</div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex items-center text-slate-300 mb-2">
                <Users className="w-4 h-4 mr-2" /> Jugadores Clave
              </div>
              <div className="bg-slate-800/50 p-3 rounded-lg text-sm text-slate-300">
                <p>• Messi (Inter Miami) - Excelente forma, 5 goles en 3 partidos</p>
                <p>• Mac Allister (Liverpool) - Titular indiscutible</p>
              </div>
            </div>

            <div>
              <div className="flex items-center text-amber-400 mb-2">
                <AlertTriangle className="w-4 h-4 mr-2" /> Reporte de Lesiones
              </div>
              <div className="bg-amber-500/10 border border-amber-500/20 p-3 rounded-lg text-sm text-amber-200">
                Ninguna lesión crítica reportada en el once inicial.
              </div>
            </div>
          </div>
        </div>

        {/* Away Team */}
        <div className="glass-panel p-6 border-t-4 border-t-red-500">
          <div className="flex justify-between items-start mb-6">
            <div>
              <h3 className="text-2xl font-bold text-slate-100">Arabia Saudita</h3>
              <p className="text-red-400 font-medium mt-1">Forma: L D L W L</p>
            </div>
            <div className="text-right">
              <div className="text-sm text-slate-400">Probabilidad de Victoria</div>
              <div className="text-2xl font-bold text-red-400">8%</div>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <div className="flex items-center text-slate-300 mb-2">
                <Users className="w-4 h-4 mr-2" /> Rendimiento Reciente
              </div>
              <div className="bg-slate-800/50 p-3 rounded-lg text-sm text-slate-300">
                Defensa vulnerable en transiciones rápidas. Promedio de 2.1 goles concedidos en últimos 5 partidos.
              </div>
            </div>

            <div>
              <div className="flex items-center text-amber-400 mb-2">
                <AlertTriangle className="w-4 h-4 mr-2" /> Reporte de Lesiones
              </div>
              <div className="bg-amber-500/10 border border-amber-500/20 p-3 rounded-lg text-sm text-amber-200">
                Al-Dawsari (Duda por molestia muscular).
              </div>
            </div>
          </div>
        </div>
      </div>

      <div className="mt-6 glass-panel p-6">
        <h3 className="text-xl font-bold text-slate-100 mb-4">Veredicto del Modelo (Value Bet)</h3>
        <p className="text-slate-300 leading-relaxed">
          La probabilidad real estimada para la victoria de Argentina es del 78%, mientras que la cuota actual en 1xBet (1.15) implica una probabilidad del 86%. Matemáticamente no existe un valor ('Value') gigantesco, sin embargo, dada la robustez del equipo y la ausencia de lesiones, se califica como <span className="text-emerald-400 font-bold">Alta Confianza</span> para parleys o apuestas combinadas (fijinis).
        </p>
      </div>
    </div>
  );
}
