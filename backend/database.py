import os
import json
import sys
from typing import List, Dict, Any, Optional

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

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("MONGO_DB_NAME", "sagar_drishti")

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
        # Try PyMongo connection first
        try:
            import pymongo
            client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=1500)
            # Test connection
            client.admin.command('ping')
            self.db = client[DB_NAME]
            self.use_mongo = True
            print(f"MongoDB connected successfully to {MONGO_URI}/{DB_NAME}")
            
            # Create 2dsphere index on float location
            self.db.argo_profiles.create_index([("location", pymongo.GEOSPHERE)])
            self.db.gliders.create_index([("location", pymongo.GEOSPHERE)])
            print("MongoDB 2dsphere geospatial index created on 'location'.")
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
                self.memory_store = data
                print(f"Loaded {len(data.get('profiles', []))} profiles into DatabaseManager!")

            if self.use_mongo and self.db is not None:
                try:
                    # Clear existing collections
                    self.db.argo_profiles.delete_many({})
                    self.db.gliders.delete_many({})
                    
                    # Convert to GeoJSON documents for 2dsphere indexing
                    mongo_profiles = []
                    for p in data.get("profiles", []):
                        doc = dict(p)
                        doc["location"] = {
                            "type": "Point",
                            "coordinates": [p["longitude"], p["latitude"]]
                        }
                        mongo_profiles.append(doc)

                    if mongo_profiles:
                        self.db.argo_profiles.insert_many(mongo_profiles)

                    mongo_gliders = []
                    for g in data.get("gliders", []):
                        doc = dict(g)
                        doc["location"] = {
                            "type": "Point",
                            "coordinates": [g["current_lon"], g["current_lat"]]
                        }
                        mongo_gliders.append(doc)
                    if mongo_gliders:
                        self.db.gliders.insert_many(mongo_gliders)

                    print(f"Ingested {len(mongo_profiles)} float documents into MongoDB with 2dsphere index!")
                except Exception as ex:
                    print(f"MongoDB insertion warning: {ex}")

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
