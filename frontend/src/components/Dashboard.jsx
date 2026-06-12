import React, { useState, useEffect } from 'react';
import axios from 'axios';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Area, AreaChart } from 'recharts';
import { Wallet, TrendingUp, CheckCircle, XCircle } from 'lucide-react';

export default function Dashboard() {
  const [data, setData] = useState({
    bankroll: 0,
    initial: 100,
    yield_percent: 0,
    win_rate: 0,
    history: []
  });

  useEffect(() => {
    const fetchPaperTrading = async () => {
      try {
        const response = await axios.get('http://127.0.0.1:8000/api/paper-trading');
        setData(response.data);
      } catch (error) {
        console.error("Error fetching paper trading data:", error);
      }
    };
    fetchPaperTrading();
  }, []);

  return (
    <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
      <header className="mb-8">
        <h2 className="text-3xl font-bold text-slate-100">Simulación Paper Trading</h2>
        <p className="text-slate-400">Rastreo de bankroll basado en apuestas fijinis (cuotas 1.1 - 1.5)</p>
      </header>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-8">
        <div className="glass-panel p-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400 font-medium mb-1">Capital Actual</p>
            <h3 className="text-3xl font-bold text-slate-100">${data.bankroll.toFixed(2)}</h3>
          </div>
          <div className="bg-emerald-500/20 p-3 rounded-xl text-emerald-400">
            <Wallet size={24} />
          </div>
        </div>
        
        <div className="glass-panel p-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400 font-medium mb-1">Crecimiento (Yield)</p>
            <h3 className="text-3xl font-bold text-emerald-400">+{data.yield_percent.toFixed(1)}%</h3>
          </div>
          <div className="bg-emerald-500/20 p-3 rounded-xl text-emerald-400">
            <TrendingUp size={24} />
          </div>
        </div>

        <div className="glass-panel p-6 flex items-center justify-between">
          <div>
            <p className="text-sm text-slate-400 font-medium mb-1">Win Rate (Fijinis)</p>
            <h3 className="text-3xl font-bold text-blue-400">{data.win_rate}%</h3>
          </div>
          <div className="flex -space-x-2">
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 z-20 ring-2 ring-slate-900"><CheckCircle size={16}/></div>
            <div className="w-8 h-8 rounded-full bg-emerald-500/20 flex items-center justify-center text-emerald-400 z-10 ring-2 ring-slate-900"><CheckCircle size={16}/></div>
            <div className="w-8 h-8 rounded-full bg-red-500/20 flex items-center justify-center text-red-400 z-0 ring-2 ring-slate-900"><XCircle size={16}/></div>
          </div>
        </div>
      </div>

      <div className="glass-panel p-6">
        <h3 className="text-lg font-semibold text-slate-200 mb-6">Evolución del Bankroll</h3>
        <div className="h-80 w-full">
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data.history}>
              <defs>
                <linearGradient id="colorBalance" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#10B981" stopOpacity={0.3}/>
                  <stop offset="95%" stopColor="#10B981" stopOpacity={0}/>
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" vertical={false} />
              <XAxis dataKey="day" stroke="#64748B" tick={{fill: '#64748B'}} axisLine={false} tickLine={false} />
              <YAxis stroke="#64748B" tick={{fill: '#64748B'}} axisLine={false} tickLine={false} domain={['dataMin - 5', 'dataMax + 5']} />
              <Tooltip 
                contentStyle={{ backgroundColor: '#0F172A', borderColor: '#1E293B', color: '#F8FAFC', borderRadius: '0.5rem' }}
                itemStyle={{ color: '#10B981' }}
              />
              <Area type="monotone" dataKey="balance" stroke="#10B981" strokeWidth={3} fillOpacity={1} fill="url(#colorBalance)" />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
