import React from 'react';
import { X, AlertTriangle, MapPin, Compass, ShieldAlert, ChevronRight } from 'lucide-react';

interface AnomalyListDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  anomalies: any[];
  onFlyTo: (lat: number, lon: number, floatId: string) => void;
}

export const AnomalyListDrawer: React.FC<AnomalyListDrawerProps> = ({
  isOpen,
  onClose,
  anomalies,
  onFlyTo
}) => {
  if (!isOpen) return null;

  return (
    <div className="fixed top-20 left-88 z-30 w-96 max-h-[calc(100vh-100px)] overflow-y-auto glass-panel-red rounded-2xl border border-red-500/50 shadow-glass p-5 text-xs space-y-4 animate-in slide-in-from-left duration-300">
      {/* Header */}
      <div className="flex items-start justify-between border-b border-red-900/60 pb-3">
        <div className="flex items-center space-x-2 text-red-400 font-bold text-sm">
          <AlertTriangle className="w-5 h-5 animate-pulse" />
          <span>Active Ocean Anomalies ({anomalies.length})</span>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-lg bg-red-950 border border-red-800 text-red-400 hover:text-white cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      <p className="text-[11px] text-red-200">
        Regional Z-score engine comparing float profile readings against monthly climatology baseline (mean ± std).
      </p>

      {/* Anomalies List */}
      <div className="space-y-3">
        {anomalies.map((item, idx) => {
          const detail = item.anomaly_detail;
          return (
            <div
              key={idx}
              className="p-3 rounded-xl bg-ocean-navy/90 border border-red-500/40 hover:border-red-400 transition-all space-y-2 group cursor-pointer"
              onClick={() => onFlyTo(item.latitude, item.longitude, item.float_id)}
            >
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="font-bold text-white text-xs">{item.float_id}</span>
                  <span className="text-[10px] px-1.5 py-0.2 rounded bg-red-950 text-red-300 border border-red-700">
                    {detail.severity} (|z| = {Math.abs(detail.z_score)}σ)
                  </span>
                </div>
                <div className="flex items-center space-x-1 text-cyan-400 text-[10px] group-hover:translate-x-1 transition-transform">
                  <span>Fly To</span>
                  <ChevronRight className="w-3 h-3" />
                </div>
              </div>

              <div className="flex items-center space-x-2 text-[10px] text-slate-300 font-mono">
                <MapPin className="w-3 h-3 text-india-saffron" />
                <span>{item.region}</span>
                <span>•</span>
                <span>{item.latitude.toFixed(1)}°, {item.longitude.toFixed(1)}°</span>
                <span>•</span>
                <span className="text-amber-300 font-semibold">{detail.depth}m</span>
              </div>

              <p className="text-[11px] text-slate-200 bg-red-950/40 p-2 rounded-lg border border-red-900/50 leading-normal">
                "{detail.explanation}"
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
};
