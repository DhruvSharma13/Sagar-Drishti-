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
    data_source: str  # "real" | "simulated"
    data_source_description: str
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
    data_source: str  # "real" | "simulated"
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
