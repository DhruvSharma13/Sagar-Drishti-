import os
import json
import sys
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple

sys.path.append(os.path.dirname(__file__))

try:
    from backend.models import FloatProfile, GliderTrack, ModelComparison, DashboardStats
except ImportError:
    from models import FloatProfile, GliderTrack, ModelComparison, DashboardStats

# Load .env file if present
def _load_env_file(path: str):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass

_load_env_file(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))
_load_env_file(os.path.join(os.path.dirname(__file__), ".env"))

def get_db_name() -> str:
    return os.getenv("MONGODB_DB_NAME") or os.getenv("MONGO_DB_NAME") or "sagar_drishti"

MONGO_URI = os.getenv("MONGODB_URI") or os.getenv("MONGO_URI") or "mongodb://localhost:27017"

class DatabaseManager:
    def __init__(self):
        self.use_mongo = False
        self.db = None
        self.memory_store: Dict[str, Any] = {
            "profiles": [],
            "gliders": [],
            "model_comparisons": [],
            "stats": {}
        }
        self.init_db()

    def init_db(self):
        target_db_name = get_db_name()
        try:
            import pymongo
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
            client.admin.command('ping')
            self.db = client[target_db_name]
            self.use_mongo = True
            print(f"MongoDB connected successfully to database '{target_db_name}'")
            
            # Create 2dsphere index on float & glider location
            self.db.argo_profiles.create_index([("location", pymongo.GEOSPHERE)])
            self.db.gliders.create_index([("location", pymongo.GEOSPHERE)])
            
            # Create unique compound index on sst_daily (dataset_id + date + region_id)
            self.db.sst_daily.create_index(
                [("dataset_id", pymongo.ASCENDING), ("date", pymongo.ASCENDING), ("region_id", pymongo.ASCENDING)],
                unique=True
            )
            self.db.sst_daily.create_index([("date", pymongo.ASCENDING)])

            # Create unique compound index on seed_sst
            self.db.seed_sst.create_index(
                [("dataset_id", pymongo.ASCENDING), ("date", pymongo.ASCENDING), ("region_id", pymongo.ASCENDING)],
                unique=True
            )

            # Index on ingest_runs for quick audit history queries
            self.db.ingest_runs.create_index([("started_at", pymongo.DESCENDING)])

            print("MongoDB indexes created: 2dsphere on location, unique compound index on (dataset_id, date, region_id).")
        except Exception as e:
            print(f"MongoDB not active locally ({e}). Using robust memory/cache fallback database.")
            self.use_mongo = False

        # Load cached dataset into database
        self.load_cache_into_db()

    def load_cache_into_db(self):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        cache_file = os.path.join(base_dir, "cache", "data_cache.json")
        
        if not os.path.exists(cache_file):
            print(f"Cache file '{cache_file}' not found on startup. Generating dataset...")
            try:
                from data_pipeline import generate_indian_ocean_dataset
                generate_indian_ocean_dataset()
            except Exception as ex:
                print(f"Dataset generation error: {ex}")

        if os.path.exists(cache_file):
            with open(cache_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.memory_store["profiles"] = data.get("profiles", [])
                self.memory_store["gliders"] = data.get("gliders", [])
                self.memory_store["model_comparisons"] = data.get("model_comparisons", [])
                self.memory_store["stats"] = data.get("stats", {})
                print(f"Loaded {len(data.get('profiles', []))} profiles into DatabaseManager memory store!")

            if self.use_mongo and self.db is not None:
                try:
                    # Non-destructive upserts for argo_profiles and gliders on startup
                    # (DO NOT use delete_many({}) to prevent wiping historical data)
                    for p in data.get("profiles", []):
                        doc = dict(p)
                        doc["location"] = {
                            "type": "Point",
                            "coordinates": [p["longitude"], p["latitude"]]
                        }
                        self.db.argo_profiles.update_one(
                            {"float_id": p.get("float_id")},
                            {"$set": doc},
                            upsert=True
                        )

                    for g in data.get("gliders", []):
                        doc = dict(g)
                        doc["location"] = {
                            "type": "Point",
                            "coordinates": [g["current_lon"], g["current_lat"]]
                        }
                        self.db.gliders.update_one(
                            {"glider_id": g.get("glider_id")},
                            {"$set": doc},
                            upsert=True
                        )

                    print("Ingested profile & glider documents into MongoDB via idempotent upserts (no delete_many).")
                except Exception as ex:
                    print(f"MongoDB insertion warning: {ex}")

    def save_sst_daily(self, doc_dict: Dict[str, Any]) -> str:
        """
        Upserts an sst_daily document into MongoDB and memory store.
        Key: (dataset_id, date, region_id).
        Tracks revision changes ('nrt' -> 'final').
        """
        key = {
            "dataset_id": doc_dict.get("dataset_id"),
            "date": doc_dict.get("date"),
            "region_id": doc_dict.get("region_id", "indian_ocean")
        }

        # Keep in memory store
        if "sst_daily" not in self.memory_store:
            self.memory_store["sst_daily"] = {}
        mem_key = f"{key['dataset_id']}_{key['date']}_{key['region_id']}"
        self.memory_store["sst_daily"][mem_key] = doc_dict

        if self.use_mongo and self.db is not None:
            existing = self.db.sst_daily.find_one(key)
            if existing:
                old_rev = existing.get("revision", "nrt")
                new_rev = doc_dict.get("revision", "nrt")
                if old_rev != new_rev:
                    print(f"[REVISION UPDATE] Date {key['date']}: revision updated from '{old_rev}' to '{new_rev}'")
            
            self.db.sst_daily.update_one(key, {"$set": doc_dict}, upsert=True)
            return f"Upserted sst_daily document for {key['date']} into MongoDB."
        
        return f"Saved sst_daily document for {key['date']} into memory store."

    def save_seed_sst(self, doc_dict: Dict[str, Any]):
        """Upserts a seed SST document into seed_sst collection."""
        key = {
            "dataset_id": doc_dict.get("dataset_id"),
            "date": doc_dict.get("date"),
            "region_id": doc_dict.get("region_id", "indian_ocean")
        }
        if "seed_sst" not in self.memory_store:
            self.memory_store["seed_sst"] = {}
        mem_key = f"{key['dataset_id']}_{key['date']}_{key['region_id']}"
        self.memory_store["seed_sst"][mem_key] = doc_dict

        if self.use_mongo and self.db is not None:
            self.db.seed_sst.update_one(key, {"$set": doc_dict}, upsert=True)

    def record_ingest_run(self, run_dict: Dict[str, Any]):
        """Records an ingest run document in ingest_runs collection."""
        if "ingest_runs" not in self.memory_store:
            self.memory_store["ingest_runs"] = []
        self.memory_store["ingest_runs"].append(run_dict)

        if self.use_mongo and self.db is not None:
            self.db.ingest_runs.update_one(
                {"job_id": run_dict.get("job_id")},
                {"$set": run_dict},
                upsert=True
            )

    def get_latest_sst(self) -> Dict[str, Any]:
        """
        Retrieves latest SST grid using strict fallback hierarchy:
        1. Fresh live stored SST from MongoDB sst_daily (data_source="live" if last ingest succeeded and data <= expected latency)
        2. Cached stored SST (data_source="cached" if last ingest failed or data > expected latency)
        3. Seed demo SST fallback (data_source="demo", is_seed=True, data_timestamp=None, age_hours=None, is_stale=None)
        """
        stale_threshold_days = int(os.getenv("STALE_THRESHOLD_DAYS", "3"))
        expected_latency_days = int(os.getenv("EXPECTED_LATENCY_DAYS", "3"))
        now_dt = datetime.now(timezone.utc)

        # Check last ingest run status
        last_run = None
        if self.use_mongo and self.db is not None:
            try:
                last_run = self.db.ingest_runs.find_one({}, sort=[("started_at", -1)], projection={"_id": 0})
            except Exception:
                pass
        if not last_run and "ingest_runs" in self.memory_store and self.memory_store["ingest_runs"]:
            last_run = self.memory_store["ingest_runs"][-1]

        last_run_succeeded = (last_run is not None and last_run.get("status") == "success")

        # 1. Check MongoDB sst_daily for live data (is_seed: False)
        live_doc = None
        if self.use_mongo and self.db is not None:
            try:
                live_doc = self.db.sst_daily.find_one({"is_seed": False}, sort=[("date", -1)], projection={"_id": 0})
            except Exception as ex:
                print(f"[DB SST RETRIEVAL WARNING] MongoDB error: {ex}")

        # 2. Check Memory store if not in Mongo
        if not live_doc:
            mem_sst_daily = self.memory_store.get("sst_daily", {})
            if mem_sst_daily:
                latest_key = sorted(mem_sst_daily.keys())[-1]
                cand = dict(mem_sst_daily[latest_key])
                if not cand.get("is_seed", False):
                    live_doc = cand

        if live_doc:
            dt_str = live_doc.get("data_timestamp", live_doc.get("date", ""))
            doc_dt = None
            try:
                doc_dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
            except Exception:
                pass
            
            data_ts_age = round((now_dt - doc_dt).total_seconds() / 3600.0, 1) if doc_dt else 0.0

            fetch_str = live_doc.get("fetched_at")
            fetch_dt = None
            if fetch_str:
                try:
                    fetch_dt = datetime.fromisoformat(fetch_str.replace("Z", "+00:00"))
                except Exception:
                    pass
            fetched_at_age = round((now_dt - fetch_dt).total_seconds() / 3600.0, 1) if fetch_dt else None

            is_stale = data_ts_age > (stale_threshold_days * 24.0)

            # Determine live vs cached
            if last_run_succeeded and data_ts_age <= (expected_latency_days * 24.0):
                live_doc["data_source"] = "live"
                live_doc["fallback_reason"] = None
            else:
                live_doc["data_source"] = "cached"
                reason_parts = []
                if not last_run_succeeded:
                    reason_parts.append(f"latest ingest status: '{last_run.get('status') if last_run else 'none'}'")
                if data_ts_age > (expected_latency_days * 24.0):
                    reason_parts.append(f"data age {data_ts_age:.1f}h exceeds expected latency {expected_latency_days*24}h")
                live_doc["fallback_reason"] = f"Using cached live SST data ({', '.join(reason_parts)})"

            live_doc["data_timestamp_age_hours"] = data_ts_age
            live_doc["fetched_at_age_hours"] = fetched_at_age
            live_doc["is_stale"] = is_stale
            return live_doc

        # 3. Fallback to Seed / Demo Data (data_source="demo", is_seed=True)
        seed_doc = None
        if self.use_mongo and self.db is not None:
            try:
                seed_doc = self.db.seed_sst.find_one({"is_seed": True}, sort=[("date", -1)], projection={"_id": 0})
            except Exception:
                pass

        if not seed_doc:
            from erddap_client import generate_seed_sst_grid
            seed_obj = generate_seed_sst_grid()
            seed_doc = seed_obj.model_dump() if hasattr(seed_obj, 'model_dump') else seed_obj.dict()

        seed_doc["data_source"] = "demo"
        seed_doc["is_seed"] = True
        seed_doc["fallback_reason"] = "DEMO DATA - not real measurements"
        seed_doc["data_timestamp"] = None
        seed_doc["fetched_at"] = None
        seed_doc["data_timestamp_age_hours"] = None
        seed_doc["fetched_at_age_hours"] = None
        seed_doc["is_stale"] = None
        return seed_doc

    def get_sst_by_date(self, date_str: str) -> Dict[str, Any]:
        """Queries SST document for a specific date (live sst_daily preferred, seed fallback)."""
        if self.use_mongo and self.db is not None:
            try:
                doc = self.db.sst_daily.find_one({"date": date_str}, projection={"_id": 0})
                if doc:
                    return doc
                seed = self.db.seed_sst.find_one({"date": date_str}, projection={"_id": 0})
                if seed:
                    return seed
            except Exception:
                pass

        # Check memory store
        for mem_dict in [self.memory_store.get("sst_daily", {}), self.memory_store.get("seed_sst", {})]:
            for k, doc in mem_dict.items():
                if doc.get("date") == date_str:
                    return dict(doc)

        from erddap_client import generate_seed_sst_grid
        gen_seed = generate_seed_sst_grid(date_str=date_str)
        return gen_seed.model_dump() if hasattr(gen_seed, 'model_dump') else gen_seed.dict()

    def get_sst_date_range(self) -> Tuple[Optional[str], Optional[str], int]:
        """Returns (oldest_date, newest_date, total_days_count)."""
        if self.use_mongo and self.db is not None:
            try:
                dates = self.db.sst_daily.distinct("date")
                if not dates:
                    dates = self.db.seed_sst.distinct("date")
                if dates:
                    dates_sorted = sorted(dates)
                    return dates_sorted[0], dates_sorted[-1], len(dates_sorted)
            except Exception:
                pass

        all_dates = set()
        for mem in [self.memory_store.get("sst_daily", {}), self.memory_store.get("seed_sst", {})]:
            for doc in mem.values():
                if "date" in doc:
                    all_dates.add(doc["date"])

        if all_dates:
            sorted_d = sorted(list(all_dates))
            return sorted_d[0], sorted_d[-1], len(sorted_d)
        
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return today_str, today_str, 1

    def get_status(self) -> Dict[str, Any]:
        """Returns comprehensive system and pipeline status."""
        stale_threshold_days = int(os.getenv("STALE_THRESHOLD_DAYS", "3"))
        expected_latency_days = int(os.getenv("EXPECTED_LATENCY_DAYS", "3"))
        latest_sst = self.get_latest_sst()

        # Query last ingest run
        last_succ = None
        last_fail = None
        last_err = None

        if self.use_mongo and self.db is not None:
            try:
                succ_run = self.db.ingest_runs.find_one({"status": "success"}, sort=[("started_at", -1)], projection={"_id": 0})
                if succ_run:
                    last_succ = succ_run.get("finished_at", succ_run.get("started_at"))

                fail_run = self.db.ingest_runs.find_one({"status": "failed"}, sort=[("started_at", -1)], projection={"_id": 0})
                if fail_run:
                    last_fail = fail_run.get("finished_at", fail_run.get("started_at"))
                    last_err = fail_run.get("error_message")
            except Exception:
                pass

        if not last_succ and "ingest_runs" in self.memory_store:
            for r in reversed(self.memory_store["ingest_runs"]):
                if r.get("status") == "success" and not last_succ:
                    last_succ = r.get("finished_at")
                if r.get("status") == "failed" and not last_fail:
                    last_fail = r.get("finished_at")
                    last_err = r.get("error_message")

        oldest_d, newest_d, total_days = self.get_sst_date_range()

        return {
            "dataset_id": os.getenv("ERDDAP_DATASET_ID", "ncdcOisst21NrtAgg_LonPM180"),
            "data_source": latest_sst.get("data_source", "demo"),
            "is_seed": latest_sst.get("is_seed", True),
            "data_timestamp": latest_sst.get("data_timestamp"),
            "fetched_at": latest_sst.get("fetched_at"),
            "data_timestamp_age_hours": latest_sst.get("data_timestamp_age_hours"),
            "fetched_at_age_hours": latest_sst.get("fetched_at_age_hours"),
            "is_stale": latest_sst.get("is_stale"),
            "fallback_reason": latest_sst.get("fallback_reason", "DEMO DATA - not real measurements"),
            "stale_threshold_days": stale_threshold_days,
            "expected_latency_days": expected_latency_days,
            "last_successful_fetch": last_succ,
            "last_failure": last_fail,
            "last_error_message": last_err,
            "stored_days_count": total_days,
            "oldest_stored_date": oldest_d,
            "newest_stored_date": newest_d,
            "mongodb_connection_state": "connected" if (self.use_mongo and self.db is not None) else "fallback_memory",
            "units": latest_sst.get("grid_metadata", {}).get("units", "degree_C")
        }

    def get_profiles(
        self,
        variable: Optional[str] = None,
        max_depth: Optional[float] = None,
        min_depth: Optional[float] = None,
        only_anomalies: bool = False,
        z_threshold: float = 2.0,
        region: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        results = []
        profiles_list = self.memory_store.get("profiles", [])

        if self.use_mongo and self.db is not None:
            try:
                query = {}
                if only_anomalies:
                    query["has_anomaly"] = True
                if region and region != "All":
                    query["region"] = region
                
                docs = list(self.db.argo_profiles.find(query, {"_id": 0}))
                profiles_list = docs
            except Exception:
                pass

        for p in profiles_list:
            if only_anomalies and not p.get("has_anomaly", False):
                continue
            if region and region != "All" and p.get("region") != region:
                continue

            # Filter measurements by depth slider
            filtered_meas = []
            for m in p.get("measurements", []):
                d = m.get("depth", 0)
                if min_depth is not None and d < min_depth:
                    continue
                if max_depth is not None and d > max_depth:
                    continue
                
                # Check variable presence
                if variable == "temperature" and m.get("temperature") is None:
                    continue
                if variable == "salinity" and m.get("salinity") is None:
                    continue
                if variable == "chlorophyll" and m.get("chlorophyll") is None:
                    continue

                filtered_meas.append(m)

            # If profile has valid readings within the requested range
            if filtered_meas or (max_depth is None and min_depth is None):
                p_copy = dict(p)
                p_copy["measurements"] = filtered_meas
                results.append(p_copy)

        return results

    def get_profile_by_id(self, float_id: str) -> Optional[Dict[str, Any]]:
        if self.use_mongo and self.db is not None:
            try:
                doc = self.db.argo_profiles.find_one({"float_id": float_id}, {"_id": 0})
                if doc:
                    return doc
            except Exception:
                pass

        for p in self.memory_store.get("profiles", []):
            if p.get("float_id") == float_id or p.get("wmo_id") == float_id:
                return p
        return None

    def get_gliders(self) -> List[Dict[str, Any]]:
        return self.memory_store.get("gliders", [])

    def get_anomalies(self) -> List[Dict[str, Any]]:
        anomalies_list = []
        for p in self.memory_store.get("profiles", []):
            if p.get("has_anomaly"):
                for a in p.get("anomalies", []):
                    anomalies_list.append({
                        "float_id": p.get("float_id"),
                        "wmo_id": p.get("wmo_id"),
                        "data_source": p.get("data_source"),
                        "latitude": p.get("latitude"),
                        "longitude": p.get("longitude"),
                        "region": p.get("region"),
                        "timestamp": p.get("timestamp"),
                        "anomaly_detail": a
                    })
        return anomalies_list

    def get_model_comparisons(self) -> List[Dict[str, Any]]:
        return self.memory_store.get("model_comparisons", [])

    def get_stats(self) -> Dict[str, Any]:
        profiles = self.memory_store.get("profiles", [])
        total_real = len([p for p in profiles if p.get("data_source") == "real"])
        total_sim = len([p for p in profiles if p.get("data_source") == "simulated"])
        total_anom = len([p for p in profiles if p.get("has_anomaly")])

        return {
            "total_active_floats": len(profiles),
            "real_floats_count": total_real,
            "simulated_floats_count": total_sim,
            "total_gliders": len(self.memory_store.get("gliders", [])),
            "active_anomalies_count": total_anom,
            "last_sync_time": self.memory_store.get("stats", {}).get("last_sync_time", "2026-09-10 22:00:00 UTC"),
            "bounding_box": {"min_lat": -30.0, "max_lat": 30.0, "min_lon": 40.0, "max_lon": 100.0},
            "database_engine": "MongoDB (2dsphere)" if self.use_mongo else "Embedded Geo-JSON Store"
        }

db_manager = DatabaseManager()
