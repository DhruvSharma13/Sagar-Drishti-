# Sagar Drishti (सागर दृष्टि) — 3D Ocean Data & Regional Anomaly Detection Platform

[![React](https://img.shields.io/badge/React-18.x-blue.svg)](https://reactjs.org/)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.x-blue.svg)](https://www.typescriptlang.org/)
[![Vite](https://img.shields.io/badge/Vite-5.x-646CFF.svg)](https://vitejs.dev/)
[![Cesium](https://img.shields.io/badge/CesiumJS-1.121-green.svg)](https://cesium.com/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110.0-009688.svg)](https://fastapi.tiangolo.com/)
[![MongoDB](https://img.shields.io/badge/MongoDB-Atlas%20%2F%202dsphere-47A248.svg)](https://www.mongodb.com/)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind_CSS-3.x-38B2AC.svg)](https://tailwindcss.com/)

**Sagar Drishti (सागर दृष्टि)** is an advanced 3D oceanographic visualization and regional anomaly detection platform designed for scientists and researchers focusing on the Indian Ocean region (Arabian Sea, Bay of Bengal, Equatorial & Southern Indian Ocean). It integrates in-situ ARGO float profiles, glider trajectories, and hydrodynamic ocean models with real-time statistical anomaly analysis and daily Sea Surface Temperature (SST) satellite grids.

---

## 🌊 System Architecture & Data Pipeline Flow

```mermaid
flowchart TD
    subgraph Live Ingestion Engine (GitHub Actions / Standalone)
        A["NOAA CoastWatch ERDDAP\n(ncdcOisst21NrtAgg_LonPM180)"] -->|Fetch & Validate| B["backend/run_ingest.py"]
        B -->|Distributed MongoDB Lock| C["MongoDB Atlas\n(sst_daily collection)"]
        B -->|Retention Cleanup (>180d)| C
    end

    subgraph Backend API (FastAPI)
        C --> D["4-Tier Fallback Hierarchy\n(DatabaseManager.get_latest_sst)"]
        D -->|Tier 1: Fresh Live| E["data_source: live"]
        D -->|Tier 2: Cached Mongo| F["data_source: cached"]
        D -->|Tier 3: Cached Memory| G["data_source: cached (memory)"]
        D -->|Tier 4: Seed Baseline| H["data_source: demo (is_seed: true)"]
        E & F & G & H --> I["REST Endpoints\n(/api/status, /api/sst/latest, /api/probe)"]
    end

    subgraph Frontend Client (React + Cesium 3D)
        I --> J["API-Driven UI Status Badges\n(LIVE / CACHED / DEMO / STALE)"]
        I --> K["Time Slider & Point Probe Tool"]
    end
```

---

## 🛡️ 4-Tier Fallback Hierarchy & Provenance Metadata

1. **`live` (Green Badge)**: Active when the latest ingestion run in `ingest_runs` succeeded AND the stored SST measurement timestamp is within expected latency (`EXPECTED_LATENCY_DAYS`, default: 3 days).
2. **`cached` (Yellow Badge)**: Active when the latest ingestion run failed OR stored measurement age exceeds expected latency threshold.
3. **`demo` (Orange Badge & Top Banner)**: Active when no live ERDDAP measurements exist in the database. Defaults to seed grid baseline. Displays prominent top banner: `⚠️ DEMO DATA - not real measurements`.
4. **`STALE` (Warning Tag)**: Triggered when measurement date exceeds `STALE_THRESHOLD_DAYS` (default: 3 days).

---

## 📋 Environment Variables Reference

All environment variables read across the codebase are documented in `.env.example`:

| Environment Variable | Description | Default Value |
| :--- | :--- | :--- |
| `MONGODB_URI` | MongoDB Atlas or local connection string | `mongodb://localhost:27017` |
| `MONGODB_DB_NAME` | Database name | `sagar_drishti` |
| `ERDDAP_BASE_URL` | NOAA CoastWatch ERDDAP base server URL | `https://coastwatch.pfeg.noaa.gov/erddap` |
| `ERDDAP_DATASET_ID` | NOAA OISST v2.1 near-real-time dataset ID | `ncdcOisst21NrtAgg_LonPM180` |
| `ERDDAP_TIMEOUT_SECONDS` | Request timeout in seconds for ERDDAP queries | `90` |
| `REGION_MIN_LAT` | Regional bounding box minimum latitude | `-30.0` |
| `REGION_MAX_LAT` | Regional bounding box maximum latitude | `30.0` |
| `REGION_MIN_LON` | Regional bounding box minimum longitude | `30.0` |
| `REGION_MAX_LON` | Regional bounding box maximum longitude | `120.0` |
| `EXPECTED_LATENCY_DAYS` | Expected latency threshold before data is marked 'cached' | `3` |
| `STALE_THRESHOLD_DAYS` | Age threshold in days after which data is marked 'stale' | `3` |
| `RETENTION_WINDOW_DAYS` | Retention window for live SST grids (purges > 180d) | `180` |
| `MAX_BACKFILL_DAYS_PER_RUN` | Maximum missing days backfilled per ingest run | `7` |
| `INGEST_LOCK_TTL_SECONDS` | Distributed lock expiry duration in seconds | `1800` (30 minutes) |
| `MIN_HISTORY_DAYS` | Minimum stored history days for secondary rolling anomalies | `30` |
| `ENABLE_BACKEND_SCHEDULER` | Toggle optional in-backend scheduler loop inside FastAPI | `false` |

---

## 🤖 GitHub Actions Scheduled Ingestion Setup

The repository includes a GitHub Actions workflow at `.github/workflows/ingest.yml` that runs on a daily schedule (`0 2 * * *`) and via manual trigger (`workflow_dispatch`).

### Workflow Features:
- Executes `python backend/run_ingest.py`.
- Acquires distributed lock with 30-minute default TTL and active renewal during backfill.
- Backfills up to 7 missing days per run within the 180-day retention window.
- Purges live SST documents older than 180 days (never touches seed data).
- Securely loads secrets (`MONGODB_URI: ${{ secrets.MONGODB_URI }}`).

---

## 🧪 Testing Suite Execution

Both unit test suites run on an isolated test database (`sagar_drishti_test`) and mock network calls so zero live requests hit NOAA during testing:

```bash
# Execute Phase 2 Fallback Test Suite
python backend/test_phase2_fallback.py

# Execute Phase 3 Pipeline, Lock & Retention Test Suite (Mocked network)
python backend/test_phase3.py
```

---

## 👤 Author & License

Developed as part of the **Sagar Drishti (सागर दृष्टि)** initiative for Indian Ocean oceanographic visualization and monitoring. Special thanks to **INCOIS (Indian National Centre for Ocean Information Services)** and **NOAA CoastWatch ERDDAP** for ocean data standards.

**Dhruv Sharma**  
GitHub: [@DhruvSharma13](https://github.com/DhruvSharma13)
