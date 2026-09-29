import { FloatProfile, GliderTrack, ModelComparison, DashboardStats, OceanGridPoint } from '../types/ocean';

const API_BASE = 'http://127.0.0.1:8000/api';

export async function fetchStats(): Promise<DashboardStats> {
  const res = await fetch(`${API_BASE}/stats`);
  if (!res.ok) throw new Error('Failed to fetch dashboard stats');
  return res.json();
}

export async function fetchFloats(params?: {
  variable?: string;
  min_depth?: number;
  max_depth?: number;
  only_anomalies?: boolean;
  z_threshold?: number;
  region?: string;
}): Promise<{ count: number; profiles: FloatProfile[] }> {
  const searchParams = new URLSearchParams();
  if (params?.variable && params.variable !== 'all') searchParams.append('variable', params.variable);
  if (params?.min_depth !== undefined) searchParams.append('min_depth', params.min_depth.toString());
  if (params?.max_depth !== undefined) searchParams.append('max_depth', params.max_depth.toString());
  if (params?.only_anomalies) searchParams.append('only_anomalies', 'true');
  if (params?.z_threshold) searchParams.append('z_threshold', params.z_threshold.toString());
  if (params?.region && params.region !== 'All') searchParams.append('region', params.region);

  const res = await fetch(`${API_BASE}/floats?${searchParams.toString()}`);
  if (!res.ok) throw new Error('Failed to fetch float profiles');
  return res.json();
}

export async function fetchFloatDetail(floatId: string): Promise<FloatProfile> {
  const res = await fetch(`${API_BASE}/floats/${encodeURIComponent(floatId)}`);
  if (!res.ok) throw new Error(`Failed to fetch float detail for ${floatId}`);
  return res.json();
}

export async function fetchGliders(): Promise<{ count: number; gliders: GliderTrack[] }> {
  const res = await fetch(`${API_BASE}/gliders`);
  if (!res.ok) throw new Error('Failed to fetch gliders');
  return res.json();
}

export async function fetchAnomalies(): Promise<{ count: number; anomalies: any[] }> {
  const res = await fetch(`${API_BASE}/anomalies`);
  if (!res.ok) throw new Error('Failed to fetch anomalies');
  return res.json();
}

export async function fetchModelCompare(): Promise<{ count: number; comparisons: ModelComparison[] }> {
  const res = await fetch(`${API_BASE}/compare`);
  if (!res.ok) throw new Error('Failed to fetch model comparison');
  return res.json();
}

export async function fetchOceanGrid(variable: string, depth: number): Promise<{ grid_points: OceanGridPoint[] }> {
  const res = await fetch(`${API_BASE}/grid?variable=${variable}&depth=${depth}`);
  if (!res.ok) throw new Error('Failed to fetch ocean surface grid');
  return res.json();
}

export async function fetchSSTDateRange(): Promise<{
  oldest_stored_date: string;
  newest_stored_date: string;
  stored_days_count: number;
  data_source: string;
  is_seed: boolean;
}> {
  const res = await fetch(`${API_BASE}/sst/range`);
  if (!res.ok) throw new Error('Failed to fetch SST date range');
  return res.json();
}

export async function fetchProbePoint(lat: number, lon: number, date?: string): Promise<{
  requested_lat: number;
  requested_lon: number;
  nearest_lat: number;
  nearest_lon: number;
  date?: string;
  sst_value?: number | null;
  anom_value?: number | null;
  units: string;
  data_source: string;
  is_seed: boolean;
  fallback_reason?: string;
  time_series: Array<{ date?: string; sst?: number; anom?: number }>;
}> {
  const url = date
    ? `${API_BASE}/probe?lat=${lat}&lon=${lon}&date=${encodeURIComponent(date)}`
    : `${API_BASE}/probe?lat=${lat}&lon=${lon}`;
  const res = await fetch(url);
  if (!res.ok) throw new Error('Failed to probe point location');
  return res.json();
}

export async function triggerSync(): Promise<any> {
  const res = await fetch(`${API_BASE}/sync`, { method: 'POST' });
  if (!res.ok) throw new Error('Failed to sync data');
  return res.json();
}
