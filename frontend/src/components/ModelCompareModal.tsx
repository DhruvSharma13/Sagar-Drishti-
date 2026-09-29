import React from 'react';
import { ModelComparison } from '../types/ocean';
import { X, Layers, CheckCircle2, Database, ArrowRight, ShieldCheck, Cpu } from 'lucide-react';

interface ModelCompareModalProps {
  isOpen: boolean;
  onClose: () => void;
  comparisons: ModelComparison[];
}

export const ModelCompareModal: React.FC<ModelCompareModalProps> = ({ isOpen, onClose, comparisons }) => {
  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-md p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-4xl max-h-[85vh] glass-panel-glow rounded-2xl border border-cyan-500/30 p-6 flex flex-col space-y-4 shadow-glass">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-700/80 pb-3">
          <div className="flex items-center space-x-3">
            <div className="p-2 rounded-xl bg-cyan-950 border border-cyan-500/40 text-cyan-400">
              <Layers className="w-6 h-6" />
            </div>
            <div>
              <h2 className="text-lg font-bold text-white tracking-wide">
                Ocean State Model vs. Argo Observation Compare View
              </h2>
              <p className="text-xs text-slate-300">
                INCOIS Ocean Forecast Model predictions evaluated against live in-situ buoy profile measurements
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg bg-ocean-navy border border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-white cursor-pointer transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Banner Explaining Data Sources */}
        <div className="p-3 rounded-xl bg-slate-900/90 border border-slate-700 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-2">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span className="text-slate-300 font-medium">Data Integrity Status:</span>
          </div>
          <div className="flex items-center space-x-3">
            <span className="px-2.5 py-1 rounded bg-emerald-950 text-emerald-300 border border-emerald-500/40 font-semibold flex items-center space-x-1">
              <CheckCircle2 className="w-3.5 h-3.5 mr-1" /> Argo Observation (Real / In-Situ)
            </span>
            <span className="text-slate-500">vs</span>
            <span className="px-2.5 py-1 rounded bg-amber-950 text-amber-300 border border-amber-500/40 font-semibold flex items-center space-x-1">
              <Cpu className="w-3.5 h-3.5 mr-1 text-amber-400" /> Model Forecast (Simulated)
            </span>
          </div>
        </div>

        {/* Comparisons Table */}
        <div className="flex-1 overflow-y-auto border border-slate-800 rounded-xl bg-ocean-navy/60">
          <table className="w-full text-left text-xs border-collapse">
            <thead className="sticky top-0 bg-ocean-navy border-b border-slate-700 text-slate-300 uppercase text-[10px] tracking-wider font-semibold">
              <tr>
                <th className="py-3 px-4">Float / Station</th>
                <th className="py-3 px-3">Location & Depth</th>
                <th className="py-3 px-3">Argo Observed</th>
                <th className="py-3 px-3">Model Forecast (Simulated)</th>
                <th className="py-3 px-3">Delta (Δ)</th>
                <th className="py-3 px-4">Interpretation</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/80 text-slate-200">
              {comparisons.map((c, i) => {
                const obsVal = c.observed_value !== null && c.observed_value !== undefined ? c.observed_value.toFixed(2) : 'NaN';
                const modelVal = c.model_predicted_value.toFixed(2);
                const deltaVal = c.delta;
                const isUnder = deltaVal > 0;

                return (
                  <tr key={i} className="hover:bg-ocean-card/50 transition-colors">
                    <td className="py-3 px-4 font-semibold text-slate-100">
                      <div className="flex items-center space-x-2">
                        <span>{c.float_id}</span>
                        <span className={`text-[9px] px-1.5 py-0.2 rounded ${c.data_source_obs === 'real' ? 'bg-emerald-950 text-emerald-400 border border-emerald-800' : 'bg-amber-950 text-amber-400 border border-amber-800'}`}>
                          {c.data_source_obs}
                        </span>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-mono text-[11px] text-slate-300">
                      {c.latitude.toFixed(1)}°, {c.longitude.toFixed(1)}° @ <span className="text-cyan-300">{c.depth}m</span>
                    </td>
                    <td className="py-3 px-3 font-mono font-bold text-cyan-300 text-sm">
                      {obsVal} °C
                    </td>
                    <td className="py-3 px-3 font-mono text-amber-300 font-semibold">
                      <div className="flex items-center space-x-1">
                        <span>{modelVal} °C</span>
                        <span className="text-[9px] bg-amber-950/80 text-amber-400 px-1 rounded border border-amber-600/40">Simulated</span>
                      </div>
                    </td>
                    <td className="py-3 px-3 font-mono font-bold">
                      <span className={`px-2 py-0.5 rounded text-xs ${isUnder ? 'bg-red-950 text-red-300 border border-red-500/40' : 'bg-blue-950 text-blue-300 border border-blue-500/40'}`}>
                        {isUnder ? `+${deltaVal.toFixed(2)}` : deltaVal.toFixed(2)} °C
                      </span>
                    </td>
                    <td className="py-3 px-4 text-slate-300 text-[11px]">
                      {c.interpretation}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
