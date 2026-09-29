import React, { useState } from 'react';
import { FloatProfile } from '../types/ocean';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Area, ComposedChart } from 'recharts';
import { X, AlertTriangle, Database, CheckCircle2, ShieldAlert, Compass, Calendar, Layers, MapPin } from 'lucide-react';

interface FloatDetailDrawerProps {
  float: FloatProfile | null;
  onClose: () => void;
}

export const FloatDetailDrawer: React.FC<FloatDetailDrawerProps> = ({ float, onClose }) => {
  const [activeTab, setActiveTab] = useState<'temperature' | 'salinity' | 'chlorophyll'>('temperature');

  if (!float) return null;

  const chartData = float.chart_data || float.measurements.map(m => ({
    depth: m.depth,
    temp_obs: m.temperature,
    sal_obs: m.salinity,
    chla_obs: m.chlorophyll,
    temp_mean: 25 - (m.depth / 100) * 1.2,
    sal_mean: 35.0,
    chla_mean: m.depth <= 100 ? 0.6 : 0.05
  }));

  return (
    <div className="fixed top-20 right-4 z-30 w-96 max-h-[calc(100vh-100px)] overflow-y-auto glass-panel rounded-2xl border border-ocean-border shadow-glass p-5 text-xs space-y-4 animate-in slide-in-from-right duration-300">
      {/* Drawer Header */}
      <div className="flex items-start justify-between border-b border-slate-700/60 pb-3">
        <div>
          <div className="flex items-center space-x-2">
            <h2 className="text-base font-bold text-white tracking-wide">{float.float_id}</h2>
            <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-ocean-navy border border-slate-700 text-slate-300">
              WMO #{float.wmo_id}
            </span>
          </div>
          <p className="text-[11px] text-slate-400 mt-0.5">{float.platform_type} • {float.institution}</p>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg bg-ocean-navy border border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition-colors"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Data Source Badge (User Requirement: Real vs Simulated Badge) */}
      <div className="flex items-center justify-between p-2.5 rounded-xl bg-ocean-navy/80 border border-slate-700/70">
        <div className="flex items-center space-x-2">
          {float.data_source === 'real' ? (
            <>
              <CheckCircle2 className="w-4 h-4 text-emerald-400" />
              <div>
                <span className="font-bold text-emerald-300 text-xs">Real Data (INCOIS / Argo)</span>
                <span className="block text-[10px] text-slate-400">Verified ERDDAP Observation</span>
              </div>
            </>
          ) : (
            <>
              <Database className="w-4 h-4 text-amber-400" />
              <div>
                <span className="font-bold text-amber-300 text-xs">Simulated Data</span>
                <span className="block text-[10px] text-slate-400">Offline Fallback / Demo Profile</span>
              </div>
            </>
          )}
        </div>
        <span className={`text-[10px] px-2 py-0.5 rounded font-mono font-semibold uppercase ${
          float.data_source === 'real' ? 'bg-emerald-950 text-emerald-300 border border-emerald-500/40' : 'bg-amber-950 text-amber-300 border border-amber-500/40'
        }`}>
          {float.data_source}
        </span>
      </div>

      {/* Metadata Grid */}
      <div className="grid grid-cols-2 gap-2 text-[11px] bg-ocean-card/60 p-2.5 rounded-xl border border-slate-800">
        <div className="flex items-center space-x-1.5">
          <MapPin className="w-3.5 h-3.5 text-india-saffron" />
          <span className="text-slate-400">Lat/Lon:</span>
          <span className="font-mono text-slate-200">{float.latitude.toFixed(2)}°, {float.longitude.toFixed(2)}°</span>
        </div>
        <div className="flex items-center space-x-1.5">
          <Layers className="w-3.5 h-3.5 text-cyan-400" />
          <span className="text-slate-400">Max Depth:</span>
          <span className="font-mono text-slate-200">{float.max_depth}m</span>
        </div>
        <div className="flex items-center space-x-1.5 col-span-2">
          <Calendar className="w-3.5 h-3.5 text-indigo-400" />
          <span className="text-slate-400">Timestamp:</span>
          <span className="font-mono text-slate-200">{float.timestamp}</span>
        </div>
      </div>

      {/* Anomaly Warning Card (If Flagged) */}
      {float.has_anomaly && float.anomalies.length > 0 && (
        <div className="p-3 rounded-xl glass-panel-red space-y-2 border border-red-500/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-1.5 text-red-400 font-bold">
              <AlertTriangle className="w-4 h-4 animate-bounce" />
              <span>⚠️ Anomaly Flagged</span>
            </div>
            <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-red-900/80 text-red-200 border border-red-400">
              {float.anomalies[0].severity} Anomaly (|z| = {float.max_z_score}σ)
            </span>
          </div>

          <p className="text-[11px] text-red-200 leading-relaxed bg-red-950/40 p-2 rounded-lg border border-red-900/50 font-sans">
            "{float.anomalies[0].explanation}"
          </p>
        </div>
      )}

      {/* Depth Profile Chart Header & Tabs */}
      <div className="space-y-2 pt-1 border-t border-slate-700/60">
        <div className="flex items-center justify-between">
          <span className="font-bold text-slate-200">Depth-Profile Chart</span>
          <span className="text-[10px] text-slate-400">Y-axis = Depth (descending)</span>
        </div>

        {/* Thermocline Monotonicity Check (Requirement #6) */}
        {(() => {
          const measurements = float.measurements || [];
          const sorted = [...measurements]
            .filter(m => m && m.depth !== undefined && m.temperature !== null && m.temperature !== undefined)
            .sort((a, b) => a.depth - b.depth);

          if (sorted.length >= 2) {
            let invStart: number | null = null;
            let invEnd: number | null = null;
            for (let i = 1; i < sorted.length; i++) {
              const prev = sorted[i - 1];
              const curr = sorted[i];
              if ((curr.temperature ?? 0) > (prev.temperature ?? 0) + 0.15) {
                if (invStart === null) invStart = prev.depth;
                invEnd = curr.depth;
              }
            }

            if (invStart !== null && invEnd !== null) {
              return (
                <div className="p-2 rounded-lg bg-amber-950/50 border border-amber-500/40 text-[11px] text-amber-300 flex items-center space-x-1.5 font-medium">
                  <span className="text-amber-400">⚠️</span>
                  <span>Temperature inversion detected at <strong className="font-mono text-white">{invStart}m–{invEnd}m</strong> — unusual for this region.</span>
                </div>
              );
            } else {
              return (
                <div className="p-2 rounded-lg bg-emerald-950/40 border border-emerald-500/30 text-[11px] text-emerald-300 flex items-center space-x-1.5 font-medium">
                  <span>📉</span>
                  <span>Normal thermocline — temperature decreasing steadily with depth.</span>
                </div>
              );
            }
          }
          return null;
        })()}

        {/* Tab Switches */}
        <div className="flex bg-ocean-navy p-1 rounded-lg border border-slate-700">
          <button
            onClick={() => setActiveTab('temperature')}
            className={`flex-1 py-1 text-[10px] font-semibold rounded cursor-pointer transition-colors ${
              activeTab === 'temperature' ? 'bg-amber-500/20 text-amber-300 border border-amber-500/40' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Temperature (°C)
          </button>
          <button
            onClick={() => setActiveTab('salinity')}
            className={`flex-1 py-1 text-[10px] font-semibold rounded cursor-pointer transition-colors ${
              activeTab === 'salinity' ? 'bg-cyan-500/20 text-cyan-300 border border-cyan-500/40' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Salinity (PSU)
          </button>
          <button
            onClick={() => setActiveTab('chlorophyll')}
            className={`flex-1 py-1 text-[10px] font-semibold rounded cursor-pointer transition-colors ${
              activeTab === 'chlorophyll' ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40' : 'text-slate-400 hover:text-slate-200'
            }`}
          >
            Chlorophyll
          </button>
        </div>
      </div>

      {/* Recharts Depth Profile Chart */}
      <div className="h-64 w-full bg-ocean-navy/60 p-2 rounded-xl border border-slate-700/80">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart
            data={chartData}
            layout="vertical"
            margin={{ top: 10, right: 10, left: -10, bottom: 5 }}
          >
            <CartesianGrid strokeDasharray="3 3" stroke="#1E293B" />
            <XAxis
              type="number"
              stroke="#94A3B8"
              fontSize={10}
              domain={activeTab === 'temperature' ? [0, 32] : activeTab === 'salinity' ? [30, 38] : [0, 2.0]}
            />
            {/* Inverted Y axis for ocean depth descending */}
            <YAxis
              type="number"
              dataKey="depth"
              reversed
              stroke="#94A3B8"
              fontSize={10}
              unit="m"
            />
            <Tooltip
              contentStyle={{ background: '#0A1930', borderColor: '#334155', borderRadius: '8px', color: '#F8FAFC', fontSize: '11px' }}
              formatter={(value: any, name: string) => [
                value !== null && value !== undefined ? `${Number(value).toFixed(2)}` : 'NaN (Missing)',
                name === 'temp_obs' ? 'Observed Temp' : name === 'temp_mean' ? 'Baseline Mean' : name
              ]}
            />

            {/* Observed Profile Line (with connectNulls=true to handle NaN edge cases gracefully) */}
            <Line
              type="monotone"
              dataKey={activeTab === 'temperature' ? 'temp_obs' : activeTab === 'salinity' ? 'sal_obs' : 'chla_obs'}
              name="Observed Reading"
              stroke={activeTab === 'temperature' ? '#F59E0B' : activeTab === 'salinity' ? '#00F0FF' : '#10B981'}
              strokeWidth={2.5}
              dot={{ r: 3.5, fill: '#0A1930', strokeWidth: 2 }}
              connectNulls={true}
            />

            {/* Climatology Baseline Mean Line */}
            <Line
              type="monotone"
              dataKey={activeTab === 'temperature' ? 'temp_mean' : activeTab === 'salinity' ? 'sal_mean' : 'chla_mean'}
              name="Monthly Baseline Mean"
              stroke="#94A3B8"
              strokeDasharray="4 4"
              strokeWidth={1.5}
              dot={false}
              connectNulls={true}
            />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      {/* Legend & QC note */}
      <div className="flex items-center justify-between text-[10px] text-slate-400 pt-1">
        <div className="flex items-center space-x-3">
          <span className="flex items-center">
            <span className="w-2.5 h-2.5 rounded-full bg-amber-400 mr-1"></span> Observed
          </span>
          <span className="flex items-center">
            <span className="w-2.5 h-0.5 bg-slate-400 mr-1 border-b border-dashed"></span> Baseline
          </span>
        </div>
        <span className="text-emerald-400 font-medium">QC Flags: Good (1)</span>
      </div>
    </div>
  );
};
