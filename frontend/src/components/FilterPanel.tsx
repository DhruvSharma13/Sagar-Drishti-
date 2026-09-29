import React from 'react';
import { Sliders, Filter, Thermometer, Droplets, Activity, Layers, ShieldAlert, Eye } from 'lucide-react';

interface FilterPanelProps {
  variable: string;
  setVariable: (v: string) => void;
  maxDepth: number;
  setMaxDepth: (d: number) => void;
  minDepth: number;
  setMinDepth: (d: number) => void;
  region: string;
  setRegion: (r: string) => void;
  onlyAnomalies: boolean;
  setOnlyAnomalies: (b: boolean) => void;
  zThreshold: number;
  setZThreshold: (z: number) => void;
  showGliders: boolean;
  setShowGliders: (b: boolean) => void;
  showHeatmap: boolean;
  setShowHeatmap: (b: boolean) => void;
}

export const FilterPanel: React.FC<FilterPanelProps> = ({
  variable,
  setVariable,
  maxDepth,
  setMaxDepth,
  minDepth,
  setMinDepth,
  region,
  setRegion,
  onlyAnomalies,
  setOnlyAnomalies,
  zThreshold,
  setZThreshold,
  showGliders,
  setShowGliders,
  showHeatmap,
  setShowHeatmap,
}) => {
  return (
    <div className="absolute top-20 left-6 z-20 w-80 glass-panel rounded-2xl p-4 border border-ocean-border shadow-glass text-xs space-y-4 max-h-[calc(100vh-120px)] overflow-y-auto">
      {/* Panel Header */}
      <div className="flex items-center justify-between border-b border-slate-700/60 pb-2.5">
        <div className="flex items-center space-x-2 text-cyan-400 font-bold tracking-wide">
          <Sliders className="w-4 h-4" />
          <span>Ocean Data Controls</span>
        </div>
        <span className="text-[10px] px-2 py-0.5 rounded bg-ocean-navy text-slate-300 border border-slate-700 font-mono">
          INCOIS Box
        </span>
      </div>

      {/* Variable Selector */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-semibold text-slate-300 flex items-center space-x-1.5">
          <Filter className="w-3.5 h-3.5 text-amber-400" />
          <span>Physical Parameter</span>
        </label>
        <div className="grid grid-cols-3 gap-1.5">
          <button
            onClick={() => setVariable('temperature')}
            className={`py-1.5 px-2 rounded-lg font-semibold flex flex-col items-center justify-center space-y-1 border cursor-pointer transition-all ${
              variable === 'temperature'
                ? 'bg-amber-500/20 text-amber-300 border-amber-500/50 shadow-inner'
                : 'bg-ocean-navy text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
          >
            <Thermometer className="w-3.5 h-3.5" />
            <span className="text-[10px]">Temp (°C)</span>
          </button>
          <button
            onClick={() => setVariable('salinity')}
            className={`py-1.5 px-2 rounded-lg font-semibold flex flex-col items-center justify-center space-y-1 border cursor-pointer transition-all ${
              variable === 'salinity'
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50 shadow-inner'
                : 'bg-ocean-navy text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
          >
            <Droplets className="w-3.5 h-3.5" />
            <span className="text-[10px]">Salinity</span>
          </button>
          <button
            onClick={() => setVariable('chlorophyll')}
            className={`py-1.5 px-2 rounded-lg font-semibold flex flex-col items-center justify-center space-y-1 border cursor-pointer transition-all ${
              variable === 'chlorophyll'
                ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/50 shadow-inner'
                : 'bg-ocean-navy text-slate-400 border-slate-700 hover:text-slate-200'
            }`}
          >
            <Activity className="w-3.5 h-3.5" />
            <span className="text-[10px]">Chl-a</span>
          </button>
        </div>
      </div>

      {/* Sub-Region Selector */}
      <div className="space-y-1.5">
        <label className="text-[11px] font-semibold text-slate-300">Indian Ocean Region</label>
        <select
          value={region}
          onChange={(e) => setRegion(e.target.value)}
          className="w-full bg-ocean-navy text-slate-200 border border-slate-700 rounded-lg p-2 text-xs focus:outline-none focus:border-cyan-500 cursor-pointer"
        >
          <option value="All">All Regions (Indian Ocean)</option>
          <option value="Arabian Sea">Arabian Sea</option>
          <option value="Bay of Bengal">Bay of Bengal</option>
          <option value="Equatorial Indian Ocean">Equatorial Indian Ocean</option>
          <option value="Southern Indian Ocean">Southern Indian Ocean</option>
        </select>
      </div>

      {/* Depth Slider */}
      <div className="space-y-1.5">
        <div className="flex justify-between text-[11px]">
          <span className="font-semibold text-slate-300">Depth Level Filter</span>
          <span className="font-mono text-cyan-300 font-bold">{minDepth}m – {maxDepth}m</span>
        </div>
        <input
          type="range"
          min={0}
          max={2000}
          step={50}
          value={maxDepth}
          onChange={(e) => setMaxDepth(Number(e.target.value))}
          className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-cyan-400"
        />
        <div className="flex justify-between text-[9px] text-slate-400 font-mono">
          <span>Surface (0m)</span>
          <span>1000m</span>
          <span>Abyssal (2000m)</span>
        </div>
      </div>

      {/* Anomaly Detection Controls */}
      <div className="space-y-2 pt-2 border-t border-slate-700/60">
        <div className="flex items-center justify-between">
          <label className="text-[11px] font-bold text-red-400 flex items-center space-x-1.5 cursor-pointer">
            <ShieldAlert className="w-3.5 h-3.5" />
            <span>Only Show Anomalies</span>
          </label>
          <input
            type="checkbox"
            checked={onlyAnomalies}
            onChange={(e) => setOnlyAnomalies(e.target.checked)}
            className="w-4 h-4 rounded bg-ocean-navy border-slate-700 text-red-500 focus:ring-0 cursor-pointer"
          />
        </div>

        {/* Z-Score Threshold Slider */}
        <div className="space-y-1">
          <div className="flex justify-between text-[10px]">
            <span className="text-slate-400">Z-Score Threshold (|z| ≥)</span>
            <span className="font-mono font-bold text-red-300">{zThreshold.toFixed(1)}σ</span>
          </div>
          <input
            type="range"
            min={1.0}
            max={4.0}
            step={0.1}
            value={zThreshold}
            onChange={(e) => setZThreshold(Number(e.target.value))}
            className="w-full h-1.5 bg-slate-700 rounded-lg appearance-none cursor-pointer accent-red-500"
          />
        </div>
      </div>

      {/* Toggle Layers */}
      <div className="space-y-2 pt-2 border-t border-slate-700/60">
        <span className="text-[11px] font-semibold text-slate-300 flex items-center space-x-1.5">
          <Eye className="w-3.5 h-3.5 text-indigo-400" />
          <span>Layer Overlays</span>
        </span>
        <div className="grid grid-cols-2 gap-2">
          <button
            onClick={() => setShowGliders(!showGliders)}
            className={`p-2 rounded-lg border text-center font-semibold cursor-pointer transition-all ${
              showGliders
                ? 'bg-indigo-500/20 text-indigo-300 border-indigo-500/50'
                : 'bg-ocean-navy text-slate-400 border-slate-700'
            }`}
          >
            🛸 Gliders: {showGliders ? 'ON' : 'OFF'}
          </button>
          <button
            onClick={() => {
              const nextState = !showHeatmap;
              console.log('Heatmap toggled:', nextState);
              setShowHeatmap(nextState);
            }}
            className={`p-2 rounded-lg border text-center font-semibold cursor-pointer transition-all ${
              showHeatmap
                ? 'bg-cyan-500/20 text-cyan-300 border-cyan-500/50'
                : 'bg-ocean-navy text-slate-400 border-slate-700'
            }`}
          >
            🌊 Heatmap: {showHeatmap ? 'ON' : 'OFF'}
          </button>
        </div>
      </div>
    </div>
  );
};
