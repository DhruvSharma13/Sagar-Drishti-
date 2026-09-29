import React from 'react';
import { DashboardStats } from '../types/ocean';
import { ShieldAlert, RefreshCw, Layers, Radio, Compass, AlertTriangle, Database } from 'lucide-react';

interface HeaderProps {
  stats: DashboardStats | null;
  onRefresh: () => void;
  isSyncing: boolean;
  onOpenCompare: () => void;
  onOpenAnomalies: () => void;
}

export const Header: React.FC<HeaderProps> = ({
  stats,
  onRefresh,
  isSyncing,
  onOpenCompare,
  onOpenAnomalies
}) => {
  return (
    <header className="relative z-30 w-full glass-panel border-b border-ocean-border px-4 py-3 shadow-glass flex flex-wrap items-center justify-between gap-4">
      {/* Brand & Emblem Title */}
      <div className="flex items-center space-x-3">
        <div className="relative flex items-center justify-center w-11 h-11 rounded-full bg-ocean-navy border-2 border-india-saffron shadow-glow-cyan overflow-hidden">
          {/* Subtle Ashoka Chakra SVG motif */}
          <svg className="w-8 h-8 text-india-saffron opacity-80 animate-spin-slow" viewBox="0 0 100 100">
            <circle cx="50" cy="50" r="45" fill="none" stroke="currentColor" strokeWidth="2.5" />
            <circle cx="50" cy="50" r="10" fill="currentColor" />
            {Array.from({ length: 24 }).map((_, i) => (
              <line
                key={i}
                x1="50"
                y1="50"
                x2={50 + 45 * mathCos(i * 15)}
                y2={50 + 45 * mathSin(i * 15)}
                stroke="currentColor"
                strokeWidth="1.5"
              />
            ))}
          </svg>
          <Compass className="absolute w-5 h-5 text-india-white" />
        </div>

        <div>
          <div className="flex items-center space-x-2">
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-india-saffron via-white to-india-green bg-clip-text text-transparent">
              Sagar Drishti
            </h1>
            <span className="text-xs font-semibold px-2 py-0.5 rounded bg-ocean-navy border border-india-saffron/40 text-india-saffron">
              सागर दृष्टि
            </span>
          </div>
          <p className="text-[11px] text-slate-300 font-medium tracking-wide">
            INCOIS • 3D Indian Ocean Visualization & Regional Anomaly Detection Platform
          </p>
        </div>
      </div>

      {/* Center Dashboard Stats Cards */}
      <div className="hidden lg:flex items-center space-x-3">
        <div className="px-3 py-1.5 rounded-lg bg-ocean-navy/80 border border-slate-700/60 flex items-center space-x-2 text-xs">
          <Radio className="w-4 h-4 text-ocean-cyan animate-pulse" />
          <div>
            <span className="text-slate-400 block text-[10px]">Active Floats</span>
            <span className="font-bold text-slate-100">{stats ? stats.total_active_floats : '—'}</span>
          </div>
        </div>

        <div className="px-3 py-1.5 rounded-lg bg-ocean-navy/80 border border-slate-700/60 flex items-center space-x-2 text-xs">
          <Database className="w-4 h-4 text-india-saffron" />
          <div>
            <span className="text-slate-400 block text-[10px]">INCOIS ERDDAP</span>
            <span className="font-semibold text-emerald-400 text-[11px]">
              {stats ? `${stats.real_floats_count} Real` : 'Live'}
            </span>
          </div>
        </div>

        <button
          onClick={onOpenAnomalies}
          className="px-3 py-1.5 rounded-lg bg-red-950/70 border border-red-500/50 hover:border-red-400 transition-all flex items-center space-x-2 text-xs cursor-pointer group"
        >
          <AlertTriangle className="w-4 h-4 text-red-400 group-hover:scale-110 transition-transform" />
          <div>
            <span className="text-red-300 block text-[10px] font-semibold">Anomalies Detected</span>
            <span className="font-bold text-red-400 text-sm">
              {stats ? stats.active_anomalies_count : '0'} ⚠️
            </span>
          </div>
        </button>

        <div className="px-3 py-1.5 rounded-lg bg-ocean-navy/80 border border-slate-700/60 text-xs">
          <span className="text-slate-400 block text-[10px]">Data Timestamp</span>
          <span className="font-mono text-[11px] text-cyan-300">
            {stats ? stats.last_sync_time.split(' ')[0] : '2026-09-10'}
          </span>
        </div>
      </div>

      {/* Right Controls */}
      <div className="flex items-center space-x-2">
        <button
          onClick={onOpenCompare}
          className="px-3 py-1.5 rounded-lg bg-cyan-950/80 border border-cyan-500/40 hover:bg-cyan-900/60 hover:border-cyan-400 transition-all text-xs font-semibold text-cyan-300 flex items-center space-x-1.5 cursor-pointer"
          title="Compare Ocean Model Predictions vs Buoy Observations"
        >
          <Layers className="w-4 h-4" />
          <span>Model vs Observation</span>
        </button>

        <button
          onClick={onRefresh}
          disabled={isSyncing}
          className="p-2 rounded-lg bg-ocean-card border border-ocean-border hover:border-ocean-cyan transition-all text-slate-300 hover:text-white cursor-pointer disabled:opacity-50"
          title="Resync with INCOIS ERDDAP"
        >
          <RefreshCw className={`w-4 h-4 ${isSyncing ? 'animate-spin text-india-saffron' : ''}`} />
        </button>
      </div>
    </header>
  );
};

// Simple trig helpers for SVG wheel
function mathCos(angleDeg: number) {
  return Math.cos((angleDeg * Math.PI) / 180);
}
function mathSin(angleDeg: number) {
  return Math.sin((angleDeg * Math.PI) / 180);
}
