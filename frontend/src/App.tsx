import React, { useState, useEffect } from 'react';
import { Header } from './components/Header';
import { FilterPanel } from './components/FilterPanel';
import { GlobeView } from './components/GlobeView';
import { FloatDetailDrawer } from './components/FloatDetailDrawer';
import { ModelCompareModal } from './components/ModelCompareModal';
import { AnomalyListDrawer } from './components/AnomalyListDrawer';

import { DashboardStats, FloatProfile, GliderTrack, ModelComparison, OceanGridPoint } from './types/ocean';
import { fetchStats, fetchFloats, fetchFloatDetail, fetchGliders, fetchAnomalies, fetchModelCompare, fetchOceanGrid, triggerSync } from './api/client';

export function App() {
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [floats, setFloats] = useState<FloatProfile[]>([]);
  const [gliders, setGliders] = useState<GliderTrack[]>([]);
  const [anomalies, setAnomalies] = useState<any[]>([]);
  const [comparisons, setComparisons] = useState<ModelComparison[]>([]);
  const [gridPoints, setGridPoints] = useState<OceanGridPoint[]>([]);

  const [selectedFloat, setSelectedFloat] = useState<FloatProfile | null>(null);
  const [variable, setVariable] = useState<string>('temperature');
  const [minDepth, setMinDepth] = useState<number>(0);
  const [maxDepth, setMaxDepth] = useState<number>(2000);
  const [region, setRegion] = useState<string>('All');
  const [onlyAnomalies, setOnlyAnomalies] = useState<boolean>(false);
  const [zThreshold, setZThreshold] = useState<number>(2.0);

  const [showGliders, setShowGliders] = useState<boolean>(true);
  const [showHeatmap, setShowHeatmap] = useState<boolean>(false);

  const [isCompareOpen, setIsCompareOpen] = useState<boolean>(false);
  const [isAnomaliesOpen, setIsAnomaliesOpen] = useState<boolean>(false);
  const [isSyncing, setIsSyncing] = useState<boolean>(false);

  // Initial load
  useEffect(() => {
    loadDashboardData();
  }, []);

  // Filter re-fetch
  useEffect(() => {
    loadFilteredFloats();
  }, [variable, minDepth, maxDepth, region, onlyAnomalies, zThreshold]);

  // Fetch Ocean Heatmap Grid when toggled ON or when variable/depth changes
  useEffect(() => {
    if (showHeatmap) {
      fetchOceanGrid(variable, minDepth)
        .then(res => {
          setGridPoints(res.grid_points || []);
        })
        .catch(err => {
          console.error('Error fetching ocean grid points:', err);
          setGridPoints([]);
        });
    } else {
      setGridPoints([]);
    }
  }, [showHeatmap, variable, minDepth]);

  const loadDashboardData = async () => {
    try {
      const [statsRes, glidersRes, anomaliesRes, compareRes] = await Promise.all([
        fetchStats(),
        fetchGliders(),
        fetchAnomalies(),
        fetchModelCompare()
      ]);
      setStats(statsRes);
      setGliders(glidersRes.gliders);
      setAnomalies(anomaliesRes.anomalies);
      setComparisons(compareRes.comparisons);
      loadFilteredFloats();
    } catch (err) {
      console.error('Error loading dashboard data:', err);
    }
  };

  const loadFilteredFloats = async () => {
    try {
      const res = await fetchFloats({
        variable,
        min_depth: minDepth,
        max_depth: maxDepth,
        only_anomalies: onlyAnomalies,
        z_threshold: zThreshold,
        region
      });
      setFloats(res.profiles);
    } catch (err) {
      console.error('Error loading floats:', err);
    }
  };

  const handleSelectFloat = async (f: FloatProfile | null) => {
    if (!f) {
      setSelectedFloat(null);
      return;
    }
    try {
      const fullDetail = await fetchFloatDetail(f.float_id);
      setSelectedFloat(fullDetail);
    } catch (err) {
      setSelectedFloat(f);
    }
  };

  const handleResync = async () => {
    setIsSyncing(true);
    try {
      await triggerSync();
      await loadDashboardData();
    } catch (err) {
      console.error('Sync error:', err);
    } finally {
      setIsSyncing(false);
    }
  };

  const handleFlyToAnomaly = (lat: number, lon: number, floatId: string) => {
    const target = floats.find(p => p.float_id === floatId);
    if (target) {
      handleSelectFloat(target);
    }
  };

  const handleCloseDrawer = () => {
    setSelectedFloat(null);
  };

  return (
    <div className="relative w-full h-full w-screen h-screen bg-ocean-dark overflow-hidden font-sans">
      {/* Header */}
      <Header
        stats={stats}
        onRefresh={handleResync}
        isSyncing={isSyncing}
        onOpenCompare={() => setIsCompareOpen(true)}
        onOpenAnomalies={() => setIsAnomaliesOpen(true)}
      />

      {/* Prominent Demo Data Banner */}
      {(!stats || stats.data_source === 'demo' || stats.is_seed) && (
        <div className="relative z-30 w-full bg-amber-600/90 text-amber-950 font-bold px-4 py-1 text-center text-xs tracking-wide shadow-md flex items-center justify-center space-x-2 border-b border-amber-500">
          <span>⚠️ DEMO DATA - not real measurements</span>
          <span className="font-normal opacity-90 hidden sm:inline">| NOAA ERDDAP live ingest deferred; using synthetic baseline grid & profiles</span>
        </div>
      )}

      {/* Stale Warning Banner */}
      {stats?.is_stale && (
        <div className="relative z-30 w-full bg-red-600/90 text-white font-bold px-4 py-1 text-center text-xs tracking-wide shadow-md flex items-center justify-center space-x-2 border-b border-red-500">
          <span>⚠️ STALE DATA WARNING</span>
          <span className="font-normal opacity-90">| Stored SST measurements are older than 3 days</span>
        </div>
      )}

      {/* Main 3D Globe Viewer */}
      <main className="absolute inset-0 z-10 w-full h-full">
        <GlobeView
          floats={floats}
          gliders={gliders}
          gridPoints={gridPoints}
          selectedFloat={selectedFloat}
          onSelectFloat={handleSelectFloat}
          onResetView={() => setSelectedFloat(null)}
          showGliders={showGliders}
          showHeatmap={showHeatmap}
          variable={variable}
          maxDepth={maxDepth}
        />
      </main>

      {/* Floating Filter Panel Controls */}
      <FilterPanel
        variable={variable}
        setVariable={setVariable}
        maxDepth={maxDepth}
        setMaxDepth={setMaxDepth}
        minDepth={minDepth}
        setMinDepth={setMinDepth}
        region={region}
        setRegion={setRegion}
        onlyAnomalies={onlyAnomalies}
        setOnlyAnomalies={setOnlyAnomalies}
        zThreshold={zThreshold}
        setZThreshold={setZThreshold}
        showGliders={showGliders}
        setShowGliders={setShowGliders}
        showHeatmap={showHeatmap}
        setShowHeatmap={setShowHeatmap}
      />

      {/* Side Drawer: Float Profile & Depth Chart */}
      <FloatDetailDrawer
        float={selectedFloat}
        onClose={handleCloseDrawer}
      />

      {/* Model vs Observation Comparison Modal */}
      <ModelCompareModal
        isOpen={isCompareOpen}
        onClose={() => setIsCompareOpen(false)}
        comparisons={comparisons}
      />

      {/* Anomalies Feed Drawer */}
      <AnomalyListDrawer
        isOpen={isAnomaliesOpen}
        onClose={() => setIsAnomaliesOpen(false)}
        anomalies={anomalies}
        onFlyTo={handleFlyToAnomaly}
      />
    </div>
  );
}

export default App;
