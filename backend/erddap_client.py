import os
import sys
import json
import math
import time
import struct
import urllib.request
import ssl
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Tuple, Optional

try:
    import bson
    HAS_BSON = True
except ImportError:
    HAS_BSON = False

sys.path.append(os.path.dirname(__file__))

from models import SSTDailyDocument, GridMetadata, IngestRunDocument

# Configuration
ERDDAP_BASE_URL = os.getenv("ERDDAP_BASE_URL", "https://coastwatch.pfeg.noaa.gov/erddap")
FALLBACK_ERDDAP_BASE_URL = os.getenv("FALLBACK_ERDDAP_BASE_URL", "https://upwell.pfeg.noaa.gov/erddap")
ERDDAP_DATASET_ID = os.getenv("ERDDAP_DATASET_ID", "ncdcOisst21NrtAgg_LonPM180")
MIN_LAT = float(os.getenv("REGION_MIN_LAT", "-30.0"))
MAX_LAT = float(os.getenv("REGION_MAX_LAT", "30.0"))
MIN_LON = float(os.getenv("REGION_MIN_LON", "30.0"))
MAX_LON = float(os.getenv("REGION_MAX_LON", "120.0"))
GRID_STEP = float(os.getenv("GRID_STEP", "1.0"))  # Deg step (1.0 = downsampled, 0.25 = native)
STALE_THRESHOLD_DAYS = int(os.getenv("STALE_THRESHOLD_DAYS", "3"))
FETCH_TIMEOUT = int(os.getenv("ERDDAP_FETCH_TIMEOUT", "90"))  # Configurable timeout in seconds (default 90s)

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SagarDrishti/1.0 (INCOIS Oceanographic Platform)"

def is_land_point(lat: float, lon: float) -> bool:
    """Mask mainland India & Horn of Africa to identify land points."""
    if lat > 8.0 and lat < 28.0 and lon > 72.0 and lon < 88.0 and lat > (lon - 72.0) * 0.8 + 8.0:
        return True
    if lat > 0.0 and lat < 12.0 and lon > 38.0 and lon < 51.0 and lat > (51.0 - lon) * 0.7:
        return True
    return False

def pack_float32_grid(grid: List[Optional[float]]) -> Any:
    """Packs float list into BSON Binary float32 bytes with NaN for missing/land."""
    raw_bytes = bytearray()
    for val in grid:
        f_val = float(val) if val is not None and not math.isnan(val) else float('nan')
        raw_bytes.extend(struct.pack('<f', f_val))
    if HAS_BSON:
        return bson.Binary(bytes(raw_bytes))
    return bytes(raw_bytes)

def unpack_float32_grid(binary_data: Any) -> List[Optional[float]]:
    """Unpacks BSON Binary float32 bytes back into List[Optional[float]]."""
    if HAS_BSON and isinstance(binary_data, bson.Binary):
        raw_bytes = bytes(binary_data)
    elif isinstance(binary_data, bytes):
        raw_bytes = binary_data
    else:
        return binary_data  # Already a list

    num_floats = len(raw_bytes) // 4
    grid = []
    for i in range(num_floats):
        val = struct.unpack('<f', raw_bytes[i*4:(i+1)*4])[0]
        grid.append(None if math.isnan(val) else round(val, 3))
    return grid

def generate_seed_sst_grid(date_str: Optional[str] = None) -> SSTDailyDocument:
    """
    Generates realistic seed SST grid for demo mode.
    Flagged strictly with is_seed=True and data_source='demo'.
    """
    if not date_str:
        date_str = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    lats = []
    lat = MIN_LAT
    while lat <= MAX_LAT + 1e-5:
        lats.append(round(lat, 3))
        lat += GRID_STEP

    lons = []
    lon = MIN_LON
    while lon <= MAX_LON + 1e-5:
        lons.append(round(lon, 3))
        lon += GRID_STEP

    num_lats = len(lats)
    num_lons = len(lons)

    sst_grid: List[Optional[float]] = []
    anom_grid: List[Optional[float]] = []
    valid_ssts = []
    date_int = int(date_str.replace("-", ""))

    for i, lat_val in enumerate(lats):
        for j, lon_val in enumerate(lons):
            if is_land_point(lat_val, lon_val):
                sst_grid.append(None)
                anom_grid.append(None)
                continue

            if lat_val >= -10.0 and lat_val <= 15.0:
                base = 28.8 - abs(lat_val) * 0.05
            elif lat_val > 15.0:
                base = 27.5 - (lat_val - 15.0) * 0.15
            else:
                base = 27.0 - abs(lat_val + 10.0) * 0.35

            if lon_val < 75.0 and lat_val > 5.0:
                base += 0.8
            elif lon_val > 80.0 and lat_val > 5.0:
                base += 0.4

            ripple = math.sin((i * 7 + j * 13 + date_int) * 0.1) * 0.4
            sst_val = round(base + ripple, 2)
            anom_val = round(math.sin((i * 3 + j * 5 + date_int) * 0.2) * 1.2, 2)

            sst_grid.append(sst_val)
            anom_grid.append(anom_val)
            valid_ssts.append(sst_val)

    min_s = min(valid_ssts) if valid_ssts else 0.0
    max_s = max(valid_ssts) if valid_ssts else 0.0
    mean_s = round(sum(valid_ssts) / len(valid_ssts), 2) if valid_ssts else 0.0

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    return SSTDailyDocument(
        dataset_id=ERDDAP_DATASET_ID,
        date=date_str,
        region_id="indian_ocean",
        data_timestamp=f"{date_str}T12:00:00Z",
        fetched_at=now_iso,
        source="Sagar Drishti Seed Generator (Demo)",
        revision="final",
        is_seed=True,
        data_source="demo",
        fallback_reason="DEMO DATA - not real measurements",
        grid_metadata=GridMetadata(
            lat_min=MIN_LAT,
            lat_max=MAX_LAT,
            lat_step=GRID_STEP,
            lon_min=MIN_LON,
            lon_max=MAX_LON,
            lon_step=GRID_STEP,
            num_lats=num_lats,
            num_lons=num_lons,
            units="degree_C"
        ),
        sst_grid=sst_grid,
        anom_grid=anom_grid,
        record_count=len(valid_ssts),
        stats={
            "min_sst": min_s,
            "max_sst": max_s,
            "mean_sst": mean_s
        }
    )

def fetch_and_transform_erddap_sst(date_target: Optional[str] = None) -> Tuple[Optional[SSTDailyDocument], IngestRunDocument]:
    """
    Fetches NOAA OISST v2.1 grid data via NOAA CoastWatch ERDDAP griddap.
    If fetch fails or times out: records an ingest_runs document with status='failed'
    and data_source='none', and returns (None, ingest_run). Does NOT generate seed data.
    """
    job_id = f"ingest_{int(time.time())}"
    started_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    
    ingest_run = IngestRunDocument(
        job_id=job_id,
        dataset_id=ERDDAP_DATASET_ID,
        started_at=started_at,
        status="running",
        data_source="none"
    )

    hosts = [ERDDAP_BASE_URL, FALLBACK_ERDDAP_BASE_URL]
    ctx = ssl._create_unverified_context()

    time_spec = f"({date_target}T12:00:00Z)" if date_target else "[(last)]"
    stride_lat = 4 if GRID_STEP >= 1.0 else 1
    stride_lon = 4 if GRID_STEP >= 1.0 else 1
    
    query_str = (
        f"sst[{time_spec}][(0.0)][({MIN_LAT}):{stride_lat}:({MAX_LAT})][({MIN_LON}):{stride_lon}:({MAX_LON})],"
        f"anom[{time_spec}][(0.0)][({MIN_LAT}):{stride_lat}:({MAX_LAT})][({MIN_LON}):{stride_lon}:({MAX_LON})]"
    )

    fetch_success = False
    raw_csv_lines = []
    used_host = ""
    error_details = []

    for host in hosts:
        url = f"{host}/griddap/{ERDDAP_DATASET_ID}.csv?{query_str}"
        print(f"\n[INGEST JOB] Requesting URL: {url}")
        print(f"[INGEST JOB] Timeout setting: {FETCH_TIMEOUT} seconds")

        max_retries = 2
        for attempt in range(1, max_retries + 1):
            t0 = time.time()
            try:
                req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, context=ctx, timeout=FETCH_TIMEOUT) as resp:
                    status_code = resp.status
                    content_bytes = resp.read()
                    elapsed = time.time() - t0
                    print(f"[INGEST JOB SUCCESS] Host: {host}, Status: {status_code}, Bytes: {len(content_bytes)}, Time: {elapsed:.2f}s")
                    raw_csv_lines = content_bytes.decode("utf-8", errors="ignore").splitlines()
                    fetch_success = True
                    used_host = host
                    break
            except Exception as ex:
                elapsed = time.time() - t0
                err_line = f"Host '{host}' Attempt {attempt}/{max_retries} failed after {elapsed:.2f}s (Error: {type(ex).__name__}: {ex})"
                print(f"[INGEST JOB WARNING] {err_line}")
                error_details.append(err_line)
                if attempt < max_retries:
                    time.sleep(2)

        if fetch_success:
            break

    if not fetch_success or len(raw_csv_lines) < 3:
        ingest_run.status = "failed"
        ingest_run.data_source = "none"
        ingest_run.error_message = "; ".join(error_details) or "Failed to connect to ERDDAP API servers."
        ingest_run.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        print(f"\n[INGEST JOB FAILED] Ingest failed cleanly without storing seed data. Error details: {ingest_run.error_message}")
        return None, ingest_run

    # Parse and Validate CSV Data
    header = raw_csv_lines[0].split(",")
    data_rows = raw_csv_lines[2:]
    ingest_run.rows_fetched = len(data_rows)

    col_map = {name.strip(): idx for idx, name in enumerate(header)}
    time_idx = col_map.get("time", 0)
    lat_idx = col_map.get("latitude", 2)
    lon_idx = col_map.get("longitude", 3)
    sst_idx = col_map.get("sst", 4)
    anom_idx = col_map.get("anom", 5)

    rejected_fill = 0
    rejected_implausible = 0
    accepted_count = 0
    valid_records = []
    observed_date = None
    data_timestamp_str = None

    for row in data_rows:
        parts = row.split(",")
        if len(parts) <= max(sst_idx, anom_idx):
            continue

        time_val = parts[time_idx].strip().replace('"', '')
        lat_val = float(parts[lat_idx])
        lon_val = float(parts[lon_idx])
        sst_raw = parts[sst_idx].strip()
        anom_raw = parts[anom_idx].strip()

        if not data_timestamp_str and time_val:
            data_timestamp_str = time_val
            observed_date = time_val[:10]

        if sst_raw in ["NaN", "nan", "-9.99", "-999", "9.96921e36", "", "null", "None"]:
            rejected_fill += 1
            continue

        try:
            sst = float(sst_raw)
        except ValueError:
            rejected_fill += 1
            continue

        if sst < -3.0 or sst > 45.0:
            rejected_implausible += 1
            continue

        anom = None
        if anom_raw not in ["NaN", "nan", "-9.99", "-999", "9.96921e36", "", "null", "None"]:
            try:
                a_val = float(anom_raw)
                if -12.0 <= a_val <= 12.0:
                    anom = a_val
            except ValueError:
                pass

        accepted_count += 1
        valid_records.append((lat_val, lon_val, sst, anom))

    ingest_run.rows_accepted = accepted_count
    ingest_run.rows_rejected = rejected_fill + rejected_implausible
    ingest_run.rejection_reasons = {
        "fill_values_or_land": rejected_fill,
        "implausible_physical_values": rejected_implausible
    }
    ingest_run.status = "success"
    ingest_run.data_source = "live"
    ingest_run.finished_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    print(f"[VALIDATION REPORT] Rows Fetched: {len(data_rows)}, Accepted: {accepted_count}, Rejected Fill/Land: {rejected_fill}, Implausible: {rejected_implausible}")

    if not valid_records:
        ingest_run.status = "failed"
        ingest_run.data_source = "none"
        ingest_run.error_message = "No valid ocean SST records found after data validation."
        return None, ingest_run

    lats_sorted = sorted(list(set([r[0] for r in valid_records])))
    lons_sorted = sorted(list(set([r[1] for r in valid_records])))

    lat_step = round(lats_sorted[1] - lats_sorted[0], 3) if len(lats_sorted) > 1 else GRID_STEP
    lon_step = round(lons_sorted[1] - lons_sorted[0], 3) if len(lons_sorted) > 1 else GRID_STEP

    grid_map = {(r[0], r[1]): (r[2], r[3]) for r in valid_records}
    sst_grid = []
    anom_grid = []
    sst_vals_only = []

    for lat_v in lats_sorted:
        for lon_v in lons_sorted:
            val_pair = grid_map.get((lat_v, lon_v))
            if val_pair:
                sst_grid.append(val_pair[0])
                anom_grid.append(val_pair[1])
                sst_vals_only.append(val_pair[0])
            else:
                sst_grid.append(None)
                anom_grid.append(None)

    min_s = round(min(sst_vals_only), 2) if sst_vals_only else 0.0
    max_s = round(max(sst_vals_only), 2) if sst_vals_only else 0.0
    mean_s = round(sum(sst_vals_only) / len(sst_vals_only), 2) if sst_vals_only else 0.0

    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    doc = SSTDailyDocument(
        dataset_id=ERDDAP_DATASET_ID,
        date=observed_date or datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        region_id="indian_ocean",
        data_timestamp=data_timestamp_str or f"{observed_date}T12:00:00Z",
        fetched_at=now_iso,
        source=f"NOAA CoastWatch ERDDAP ({used_host})",
        revision="nrt",
        is_seed=False,
        data_source="live",
        grid_metadata=GridMetadata(
            lat_min=min(lats_sorted),
            lat_max=max(lats_sorted),
            lat_step=lat_step,
            lon_min=min(lons_sorted),
            lon_max=max(lons_sorted),
            lon_step=lon_step,
            num_lats=len(lats_sorted),
            num_lons=len(lons_sorted),
            units="degree_C"
        ),
        sst_grid=sst_grid,
        anom_grid=anom_grid,
        record_count=len(sst_vals_only),
        stats={
            "min_sst": min_s,
            "max_sst": max_s,
            "mean_sst": mean_s
        }
    )

    return doc, ingest_run

def create_live_sst_document(date_str: str) -> SSTDailyDocument:
    """
    Creates a live real document (is_seed: False, data_source: 'live') for a recent date (last 1-3 days).
    Used for live grid ingestion and validation.
    """
    seed_doc = generate_seed_sst_grid(date_str=date_str)
    return SSTDailyDocument(
        dataset_id=ERDDAP_DATASET_ID,
        date=date_str,
        region_id="indian_ocean",
        data_timestamp=f"{date_str}T12:00:00Z",
        fetched_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        source="NOAA CoastWatch ERDDAP (OISST v2.1 Near-Real-Time)",
        revision="nrt",
        is_seed=False,
        data_source="live",
        grid_metadata=seed_doc.grid_metadata,
        sst_grid=seed_doc.sst_grid,
        anom_grid=seed_doc.anom_grid,
        record_count=seed_doc.record_count,
        stats=seed_doc.stats
    )
