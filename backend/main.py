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

@app.on_event("startup")
async def startup_event():
    enable_sched = os.getenv("ENABLE_BACKEND_SCHEDULER", "false").lower() == "true"
    if enable_sched:
        import asyncio
        from run_ingest import run_ingest_pipeline
        print("[SCHEDULER INFO] In-backend scheduler is ENABLED. Starting background worker task...")
        
        async def background_worker():
            while True:
                try:
                    print("[SCHEDULER RUN] Executing periodic background ingestion run...")
                    run_ingest_pipeline()
                except Exception as ex:
                    print(f"[SCHEDULER ERROR] Background ingestion exception: {ex}")
                # Sleep for 6 hours (21600 seconds)
                await asyncio.sleep(21600)

        asyncio.create_task(background_worker())
    else:
        print("[SCHEDULER INFO] In-backend scheduler is OFF (default). Ingestion will run via standalone script / GitHub Actions.")


@app.get("/")
def read_root():
    status = db_manager.get_status()
    return {
        "platform": "Sagar Drishti (सागर दृष्टि)",
        "agency": "INCOIS / Ministry of Earth Sciences (India)",
        "status": "Operational",
        "data_source": status.get("data_source", "demo"),
        "is_seed": status.get("is_seed", True),
        "fallback_reason": status.get("fallback_reason"),
        "endpoints": [
            "/api/status",
            "/api/stats",
            "/api/sst/latest",
            "/api/sst/range",
            "/api/probe",
            "/api/floats",
            "/api/floats/{float_id}",
            "/api/gliders",
            "/api/anomalies",
            "/api/compare",
            "/api/grid",
            "/api/climatology"
        ]
    }

@app.get("/api/status")
def get_system_status():
    return db_manager.get_status()

@app.get("/api/stats")
def get_stats():
    stats = db_manager.get_stats()
    sys_status = db_manager.get_status()
    stats["data_source"] = sys_status["data_source"]
    stats["is_seed"] = sys_status["is_seed"]
    stats["data_timestamp"] = sys_status["data_timestamp"]
    stats["fetched_at"] = sys_status["fetched_at"]
    stats["data_timestamp_age_hours"] = sys_status.get("data_timestamp_age_hours")
    stats["fetched_at_age_hours"] = sys_status.get("fetched_at_age_hours")
    stats["is_stale"] = sys_status.get("is_stale")
    stats["fallback_reason"] = sys_status["fallback_reason"]
    stats["dataset_id"] = sys_status["dataset_id"]
    return stats

@app.get("/api/sst/latest")
def get_latest_sst_grid():
    return db_manager.get_latest_sst()

@app.get("/api/sst/range")
def get_sst_date_range():
    oldest_d, newest_d, total_days = db_manager.get_sst_date_range()
    status = db_manager.get_status()
    return {
        "oldest_stored_date": oldest_d,
        "newest_stored_date": newest_d,
        "stored_days_count": total_days,
        "data_source": status["data_source"],
        "is_seed": status["is_seed"],
        "fallback_reason": status["fallback_reason"]
    }

@app.get("/api/probe")
def probe_point(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lon: float = Query(..., ge=-180.0, le=180.0),
    date: Optional[str] = Query(None)
):
    """Point probe returning SST value, anomaly, and time series at (lat, lon)."""
    if date:
        sst_doc = db_manager.get_sst_by_date(date)
    else:
        sst_doc = db_manager.get_latest_sst()

    meta = sst_doc.get("grid_metadata", {})
    lats_count = meta.get("num_lats", 61)
    lons_count = meta.get("num_lons", 91)
    lat_min = meta.get("lat_min", -30.0)
    lat_step = meta.get("lat_step", 1.0)
    lon_min = meta.get("lon_min", 30.0)
    lon_step = meta.get("lon_step", 1.0)

    # Find nearest grid cell
    i_lat = max(0, min(lats_count - 1, int(round((lat - lat_min) / lat_step))))
    j_lon = max(0, min(lons_count - 1, int(round((lon - lon_min) / lon_step))))
    
    nearest_lat = round(lat_min + i_lat * lat_step, 3)
    nearest_lon = round(lon_min + j_lon * lon_step, 3)

    idx = i_lat * lons_count + j_lon

    sst_grid = sst_doc.get("sst_grid", [])
    anom_grid = sst_doc.get("anom_grid", [])

    sst_val = sst_grid[idx] if idx < len(sst_grid) else None
    anom_val = anom_grid[idx] if idx < len(anom_grid) else None

    # Time series simulation / stored query
    time_series = [
        {"date": sst_doc.get("date"), "sst": sst_val, "anom": anom_val}
    ]

    return {
        "requested_lat": lat,
        "requested_lon": lon,
        "nearest_lat": nearest_lat,
        "nearest_lon": nearest_lon,
        "date": sst_doc.get("date"),
        "sst_value": sst_val,
        "anom_value": anom_val,
        "units": meta.get("units", "degree_C"),
        "data_source": sst_doc.get("data_source", "demo"),
        "is_seed": sst_doc.get("is_seed", True),
        "fallback_reason": sst_doc.get("fallback_reason", "DEMO DATA - not real measurements"),
        "time_series": time_series
    }

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
    status = db_manager.get_status()
    return {
        "count": len(profiles),
        "variable": variable or "all",
        "min_depth": min_depth,
        "max_depth": max_depth,
        "only_anomalies": only_anomalies,
        "data_source": "demo",
        "is_seed": True,
        "fallback_reason": "DEMO DATA - synthetic profile stations",
        "profiles": profiles
    }

@app.get("/api/floats/{float_id}")
def get_float_detail(float_id: str):
    profile = db_manager.get_profile_by_id(float_id)
    if not profile:
        raise HTTPException(status_code=404, detail=f"Float profile '{float_id}' not found.")
    
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
            "baseline_type": "demo baseline"
        })

    profile["chart_data"] = chart_data
    profile["baseline_label"] = "demo baseline"
    profile["data_source"] = "demo"
    profile["is_seed"] = True
    profile["fallback_reason"] = "DEMO DATA - synthetic profile"
    return profile

@app.get("/api/gliders")
def get_gliders():
    gliders = db_manager.get_gliders()
    return {
        "count": len(gliders),
        "data_source": "demo",
        "is_seed": True,
        "fallback_reason": "DEMO DATA - synthetic glider tracks",
        "gliders": gliders
    }

@app.get("/api/anomalies")
def get_anomalies():
    anomalies = db_manager.get_anomalies()
    return {
        "count": len(anomalies),
        "data_source": "demo",
        "is_seed": True,
        "baseline_label": "demo baseline",
        "fallback_reason": "DEMO DATA - synthetic anomaly detection",
        "anomalies": anomalies
    }

@app.get("/api/compare")
def get_model_compare():
    comparisons = db_manager.get_model_comparisons()
    return {
        "count": len(comparisons),
        "data_source": "demo",
        "is_seed": True,
        "fallback_reason": "DEMO DATA - synthetic model comparison",
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
        "baseline_label": "demo baseline",
        "data_source": "demo",
        "is_seed": True,
        "fallback_reason": "DEMO DATA - synthetic climatology equations",
        "baseline": baseline
    }

@app.get("/api/grid")
def get_ocean_grid(
    variable: str = Query("temperature"),
    depth: float = Query(0.0),
    date: Optional[str] = Query(None)
):
    """
    Returns 2D grid points for Cesium heatmap overlay coloring.
    Uses stored SST grid when depth==0, or climatological depth grid.
    """
    latest_sst = db_manager.get_latest_sst() if not date else db_manager.get_sst_by_date(date)
    grid = []

    # If surface depth, convert stored SST grid to point array
    if depth == 0.0 and "sst_grid" in latest_sst:
        meta = latest_sst.get("grid_metadata", {})
        lats_count = meta.get("num_lats", 61)
        lons_count = meta.get("num_lons", 91)
        lat_min = meta.get("lat_min", -30.0)
        lat_step = meta.get("lat_step", 1.0)
        lon_min = meta.get("lon_min", 30.0)
        lon_step = meta.get("lon_step", 1.0)
        sst_vals = latest_sst.get("sst_grid", [])

        for i in range(lats_count):
            lat_v = round(lat_min + i * lat_step, 3)
            for j in range(lons_count):
                lon_v = round(lon_min + j * lon_step, 3)
                idx = i * lons_count + j
                val = sst_vals[idx] if idx < len(sst_vals) else None
                if val is not None:
                    grid.append({
                        "lat": lat_v,
                        "lon": lon_v,
                        "value": val,
                        "variable": "temperature",
                        "depth": 0.0
                    })
    else:
        lats = [lat for lat in range(-25, 26, 5)]
        lons = [lon for lon in range(45, 96, 5)]
        for lat in lats:
            for lon in lons:
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
        "date": latest_sst.get("date"),
        "data_source": latest_sst.get("data_source", "demo"),
        "is_seed": latest_sst.get("is_seed", True),
        "fallback_reason": latest_sst.get("fallback_reason", "DEMO DATA - not real measurements"),
        "grid_points": grid
    }

@app.post("/api/sync")
def sync_data():
    dataset = generate_indian_ocean_dataset()
    db_manager.load_cache_into_db()
    status = db_manager.get_status()
    return {
        "status": "success",
        "message": "Data synchronized with local cache.",
        "data_source": status["data_source"],
        "is_seed": status["is_seed"],
        "fallback_reason": status["fallback_reason"],
        "stats": db_manager.get_stats()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
