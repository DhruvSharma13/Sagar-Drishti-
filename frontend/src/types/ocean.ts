export interface ProfileMeasurement {
  depth: number;
  temperature?: number | null;
  salinity?: number | null;
  chlorophyll?: number | null;
  temp_qc?: number;
  sal_qc?: number;
  chla_qc?: number;
}

export interface AnomalyDetail {
  is_anomaly: boolean;
  variable: string;
  depth: number;
  observed_value: number;
  climatology_mean: number;
  climatology_std: number;
  z_score: number;
  severity: "Moderate" | "High" | "Extreme";
  explanation: string;
}

export interface FloatProfile {
  float_id: str;
  wmo_id: string;
  platform_type: string;
  institution: string;
  data_source: "real" | "simulated";
  data_source_description: string;
  latitude: number;
  longitude: number;
  timestamp: string;
  region: string;
  max_depth: number;
  measurements: ProfileMeasurement[];
  anomalies: AnomalyDetail[];
  has_anomaly: boolean;
  max_z_score: number;
  chart_data?: Array<{
    depth: number;
    temp_obs?: number | null;
    temp_mean: number;
    temp_min: number;
    temp_max: number;
    sal_obs?: number | null;
    sal_mean: number;
    sal_min: number;
    sal_max: number;
    chla_obs?: number | null;
    chla_mean: number;
  }>;
}

export type str = string;

export interface GliderTrack {
  glider_id: string;
  name: string;
  mission: string;
  institution: string;
  data_source: "real" | "simulated";
  current_lat: number;
  current_lon: number;
  status: string;
  path: Array<{
    lat: number;
    lon: number;
    depth: number;
    time: string;
    temp: number;
    salinity: number;
  }>;
}

export interface ModelComparison {
  float_id: string;
  latitude: number;
  longitude: number;
  depth: number;
  timestamp: string;
  variable: string;
  observed_value?: number | null;
  model_predicted_value: number;
  delta: number;
  data_source_obs: "real" | "simulated";
  data_source_model: "simulated";
  model_label: string;
  interpretation: string;
}

export interface DashboardStats {
  total_active_floats: number;
  real_floats_count: number;
  simulated_floats_count: number;
  total_gliders: number;
  active_anomalies_count: number;
  last_sync_time: string;
  bounding_box: {
    min_lat: number;
    max_lat: number;
    min_lon: number;
    max_lon: number;
  };
  database_engine?: string;
  data_source?: "live" | "cached" | "demo";
  is_seed?: boolean;
  data_timestamp?: string | null;
  fetched_at?: string | null;
  data_timestamp_age_hours?: number | null;
  fetched_at_age_hours?: number | null;
  is_stale?: boolean | null;
  fallback_reason?: string | null;
  dataset_id?: string;
}

export interface OceanGridPoint {
  lat: number;
  lon: number;
  value: number;
  variable: string;
  depth: number;
}
