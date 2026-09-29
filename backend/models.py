from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

class ProfileMeasurement(BaseModel):
    depth: float
    temperature: Optional[float] = None
    salinity: Optional[float] = None
    chlorophyll: Optional[float] = None
    current_u: Optional[float] = None  # Eastward velocity m/s
    current_v: Optional[float] = None  # Northward velocity m/s
    temp_qc: int = 1  # 1=Good, 2=Probably Good, 3=Bad, 4=Corrupt
    sal_qc: int = 1
    chla_qc: int = 1

class AnomalyDetail(BaseModel):
    is_anomaly: bool
    variable: str
    depth: float
    observed_value: float
    climatology_mean: float
    climatology_std: float
    z_score: float
    severity: str  # "Moderate", "High", "Extreme"
    explanation: str

class FloatProfile(BaseModel):
    float_id: str
    wmo_id: str
    platform_type: str  # "Argo Float", "Deep Argo", "Apex Float", "Ocean Glider"
    institution: str  # "INCOIS (India)", "CSIRO", "IFREMER", "NIO"
    data_source: str  # "real" | "demo" | "simulated"
    data_source_description: str
    is_seed: bool = False
    latitude: float
    longitude: float
    timestamp: str
    region: str
    max_depth: float
    measurements: List[ProfileMeasurement]
    anomalies: List[AnomalyDetail] = Field(default_factory=list)
    has_anomaly: bool = False
    max_z_score: float = 0.0

class GliderTrack(BaseModel):
    glider_id: str
    name: str
    mission: str
    institution: str
    data_source: str  # "real" | "demo" | "simulated"
    is_seed: bool = False
    path: List[Dict[str, Any]]  # list of {lat, lon, depth, time, temp, salinity}
    current_lat: float
    current_lon: float
    status: str

class ModelComparison(BaseModel):
    float_id: str
    latitude: float
    longitude: float
    depth: float
    timestamp: str
    variable: str
    observed_value: Optional[float] = None
    model_predicted_value: float
    delta: float  # observed - model
    data_source_obs: str  # "real" or "simulated"
    data_source_model: str = "simulated"
    model_label: str = "Model Forecast (Simulated)"
    interpretation: str

class DashboardStats(BaseModel):
    total_active_floats: int
    real_floats_count: int
    simulated_floats_count: int
    total_gliders: int
    active_anomalies_count: int
    last_sync_time: str
    bounding_box: Dict[str, float]
    database_engine: Optional[str] = None
    sst_data_source: Optional[str] = "demo"  # "live" | "cached" | "demo"
    sst_data_timestamp: Optional[str] = None
    sst_fetched_at: Optional[str] = None
    sst_age_hours: Optional[float] = None
    sst_is_stale: bool = False
    sst_fallback_reason: Optional[str] = None

class GridMetadata(BaseModel):
    lat_min: float
    lat_max: float
    lat_step: float
    lon_min: float
    lon_max: float
    lon_step: float
    num_lats: int
    num_lons: int
    units: str = "degree_C"

class SSTDailyDocument(BaseModel):
    dataset_id: str
    date: str  # YYYY-MM-DD
    region_id: str  # "indian_ocean"
    data_timestamp: str  # ISO 8601
    fetched_at: str  # ISO 8601
    source: str  # "NOAA CoastWatch ERDDAP"
    revision: str = "nrt"  # "nrt" | "final"
    is_seed: bool = False
    data_source: str = "live"  # "live" | "cached" | "demo"
    fallback_reason: Optional[str] = None
    grid_metadata: GridMetadata
    sst_grid: List[Optional[float]]  # flattened row-major float32/None grid
    anom_grid: List[Optional[float]]  # flattened row-major float32/None grid
    record_count: int
    stats: Dict[str, float]  # {"min_sst": ..., "max_sst": ..., "mean_sst": ...}

class IngestRunDocument(BaseModel):
    job_id: str
    dataset_id: str
    started_at: str
    finished_at: Optional[str] = None
    status: str  # "running" | "success" | "failed"
    rows_fetched: int = 0
    rows_accepted: int = 0
    rows_rejected: int = 0
    rejection_reasons: Dict[str, int] = Field(default_factory=dict)
    error_message: Optional[str] = None
    data_source: str = "live"

