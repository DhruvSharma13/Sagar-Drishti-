import os
import sys
import math
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware

sys.path.append(os.path.dirname(__file__))

from database import db_manager
from data_pipeline import generate_indian_ocean_dataset
from anomaly_engine import get_climatology_baseline, get_region

app = FastAPI(
    title="Sagar Drishti (सागर दृष्टि) — Ocean Data & Anomaly API",
    description="INCOIS Indian Ocean 3D Visualization & Regional Anomaly Detection Engine API",
    version="1.0.0"
)

# Enable CORS for frontend Vite dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {
        "platform": "Sagar Drishti (सागर दृष्टि)",
        "agency": "INCOIS / Ministry of Earth Sciences (India)",
        "status": "Operational",
        "endpoints": [
            "/api/floats",
            "/api/floats/{float_id}",
            "/api/gliders",
            "/api/anomalies",
            "/api/compare",
            "/api/stats",
            "/api/grid",
            "/api/climatology"
        ]
    }

@app.get("/api/stats")
def get_stats():
    return db_manager.get_stats()

@app.get("/api/floats")
def get_floats(
    variable: Optional[str] = Query(None, description="temperature, salinity, chlorophyll"),
    min_depth: Optional[float] = Query(0.0, ge=0, le=2000),
    max_depth: Optional[float] = Query(2000.0, ge=0, le=2000),
    only_anomalies: bool = Query(False),
    z_threshold: float = Query(2.0, ge=1.0, le=5.0),
    region: Optional[str] = Query(None)
):
    profiles = db_manager.get_profiles(
        variable=variable,
        min_depth=min_depth,
        max_depth=max_depth,
        only_anomalies=only_anomalies,
        z_threshold=z_threshold,
        region=region
    )
    return {
        "count": len(profiles),
        "variable": variable or "all",
        "min_depth": min_depth,
        "max_depth": max_depth,
        "only_anomalies": only_anomalies,
        "profiles": profiles
    }

@app.get("/api/floats/{float_id}")
def get_float_detail(float_id: str):
    profile = db_manager.get_profile_by_id(float_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Float profile '{float_id}' not found.")
    
    # Attach regional climatology baseline envelope for depth chart rendering
    region = profile.get("region", "Arabian Sea")
    month = 8
    measurements = profile.get("measurements", [])
    
    chart_data = []
    for m in measurements:
        d = m["depth"]
        t_mean, t_std = get_climatology_baseline(region, month, d, "temperature")
        s_mean, s_std = get_climatology_baseline(region, month, d, "salinity")
        c_mean, c_std = get_climatology_baseline(region, month, d, "chlorophyll")
        
        chart_data.append({
            "depth": d,
            "temp_obs": m.get("temperature"),
            "temp_mean": t_mean,
            "temp_min": round(t_mean - 2 * t_std, 2),
            "temp_max": round(t_mean + 2 * t_std, 2),
            "sal_obs": m.get("salinity"),
            "sal_mean": s_mean,
            "sal_min": round(s_mean - 2 * s_std, 2),
            "sal_max": round(s_mean + 2 * s_std, 2),
            "chla_obs": m.get("chlorophyll"),
            "chla_mean": c_mean,
            "temp_qc": m.get("temp_qc", 1),
            "sal_qc": m.get("sal_qc", 1),
        })

    profile["chart_data"] = chart_data
    return profile

@app.get("/api/gliders")
def get_gliders():
    gliders = db_manager.get_gliders()
    return {
        "count": len(gliders),
        "gliders": gliders
    }

@app.get("/api/anomalies")
def get_anomalies():
    anomalies = db_manager.get_anomalies()
    return {
        "count": len(anomalies),
        "anomalies": anomalies
    }

@app.get("/api/compare")
def get_model_compare():
    comparisons = db_manager.get_model_comparisons()
    return {
        "count": len(comparisons),
        "comparisons": comparisons
    }

@app.get("/api/climatology")
def get_climatology(
    region: str = Query("Arabian Sea"),
    month: int = Query(8, ge=1, le=12)
):
    depths = [0, 10, 20, 50, 75, 100, 150, 200, 300, 500, 750, 1000, 1500, 2000]
    baseline = []
    for d in depths:
        t_m, t_s = get_climatology_baseline(region, month, d, "temperature")
        s_m, s_s = get_climatology_baseline(region, month, d, "salinity")
        c_m, c_s = get_climatology_baseline(region, month, d, "chlorophyll")
        baseline.append({
            "depth": d,
            "temp_mean": t_m,
            "temp_std": t_s,
            "sal_mean": s_m,
            "sal_std": s_s,
            "chla_mean": c_m,
            "chla_std": c_s
        })
    return {
        "region": region,
        "month": month,
        "baseline": baseline
    }

@app.get("/api/grid")
def get_ocean_grid(
    variable: str = Query("temperature"),
    depth: float = Query(0.0)
):
    """
    Returns a 2D raster point grid across Indian Ocean (lat -30 to 30, lon 40 to 100)
    for Cesium heatmap overlay coloring.
    """
    grid = []
    lats = [lat for lat in range(-25, 26, 5)]
    lons = [lon for lon in range(45, 96, 5)]
    
    for lat in lats:
        for lon in lons:
            # Skip land points roughly (e.g. mainland India lat 8-30 lon 72-88)
            if (lat > 8 and lat < 28 and lon > 72 and lon < 88 and lat > (lon - 72) * 0.8 + 8):
                continue
            
            region = get_region(lat, lon)
            mean, std = get_climatology_baseline(region, 8, depth, variable)
            
            grid.append({
                "lat": lat,
                "lon": lon,
                "value": mean,
                "variable": variable,
                "depth": depth
            })

    return {
        "variable": variable,
        "depth": depth,
        "grid_points": grid
    }

@app.post("/api/sync")
def sync_data():
    dataset = generate_indian_ocean_dataset()
    db_manager.load_cache_into_db()
    return {
        "status": "success",
        "message": "Data synchronized with INCOIS ERDDAP / local cache.",
        "stats": db_manager.get_stats()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
