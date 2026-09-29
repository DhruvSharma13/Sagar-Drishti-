import os
import sys

# FORCE TEST DATABASE ENVIRONMENT VARIABLE AT TOP LEVEL
os.environ["MONGODB_DB_NAME"] = "sagar_drishti_test"
os.environ["MONGO_DB_NAME"] = "sagar_drishti_test"

import unittest
from datetime import datetime, timezone, timedelta
from fastapi.testclient import TestClient

sys.path.append(os.path.dirname(__file__))

from main import app
from database import db_manager

class TestPhase2Fallback(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_api_status_structure(self):
        """Verify /api/status returns provenance metadata and pipeline state."""
        response = self.client.get("/api/status")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("data_source", data)
        self.assertIn("is_seed", data)
        self.assertIn("fallback_reason", data)
        self.assertIn("stored_days_count", data)
        self.assertIn("mongodb_connection_state", data)
        self.assertIn("dataset_id", data)
        
        print(f"\n[PASS] /api/status endpoint response:\n{data}")

    def test_02_api_stats_provenance(self):
        """Verify /api/stats includes dataset provenance tags."""
        response = self.client.get("/api/stats")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("data_source", data)
        self.assertIn("is_seed", data)
        self.assertIn("fallback_reason", data)
        self.assertIn("total_active_floats", data)
        print(f"\n[PASS] /api/stats provenance metadata:\n  data_source: {data.get('data_source')}\n  is_seed: {data.get('is_seed')}\n  fallback_reason: {data.get('fallback_reason')}")

    def test_03_demo_fallback_when_no_live_data(self):
        """Verify that when no live ERDDAP data is present, get_latest_sst() falls back to demo data cleanly."""
        latest = db_manager.get_latest_sst()
        
        # When no live document (is_seed: False) is in DB, fallback must be 'demo'
        self.assertEqual(latest.get("data_source"), "demo")
        self.assertTrue(latest.get("is_seed"))
        self.assertIn("DEMO DATA", latest.get("fallback_reason", ""))
        print(f"\n[PASS] Demo Fallback Verified:\n  data_source: {latest.get('data_source')}\n  is_seed: {latest.get('is_seed')}\n  fallback_reason: {latest.get('fallback_reason')}")

    def test_04_probe_endpoint(self):
        """Verify /api/probe lat/lon querying and provenance fields."""
        response = self.client.get("/api/probe?lat=0.0&lon=60.0")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertEqual(data["requested_lat"], 0.0)
        self.assertEqual(data["requested_lon"], 60.0)
        self.assertIn("sst_value", data)
        self.assertIn("anom_value", data)
        self.assertIn("data_source", data)
        self.assertIn("is_seed", data)
        self.assertIn("fallback_reason", data)
        print(f"\n[PASS] /api/probe query at (0, 60):\n  sst_value: {data.get('sst_value')} C, anom_value: {data.get('anom_value')}, source: {data.get('data_source')}")

    def test_05_sst_range_endpoint(self):
        """Verify /api/sst/range returns stored bounds and total days."""
        response = self.client.get("/api/sst/range")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        
        self.assertIn("oldest_stored_date", data)
        self.assertIn("newest_stored_date", data)
        self.assertIn("stored_days_count", data)
        print(f"\n[PASS] /api/sst/range output:\n  {data}")

    def test_06_synthetic_climatology_and_argo_labels(self):
        """Verify synthetic endpoints return explicit 'demo baseline' / 'demo' labels."""
        # /api/climatology
        res_clim = self.client.get("/api/climatology?region=Arabian%20Sea&month=8")
        self.assertEqual(res_clim.status_code, 200)
        clim_data = res_clim.json()
        self.assertEqual(clim_data.get("baseline_label"), "demo baseline")
        self.assertEqual(clim_data.get("data_source"), "demo")

        # /api/floats/{float_id}
        res_floats = self.client.get("/api/floats")
        self.assertEqual(res_floats.status_code, 200)
        floats_data = res_floats.json()
        if floats_data.get("profiles"):
            float_id = floats_data["profiles"][0]["float_id"]
            res_single = self.client.get(f"/api/floats/{float_id}")
            self.assertEqual(res_single.status_code, 200)
            single_data = res_single.json()
            self.assertEqual(single_data.get("baseline_label"), "demo baseline")
            self.assertEqual(single_data.get("data_source"), "demo")

        print("\n[PASS] All synthetic endpoints correctly labeled with 'demo baseline' and 'demo' source!")

    def test_07_live_data_tier_resolution(self):
        """Simulate adding a live document (is_seed=False) and verify fallback hierarchy resolves to live/cached."""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        mock_live_doc = {
            "dataset_id": "ncdcOisst21NrtAgg_LonPM180",
            "date": now_str,
            "region_id": "indian_ocean",
            "data_timestamp": datetime.now(timezone.utc).isoformat(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "data_source": "live",
            "is_seed": False,
            "revision": "nrt",
            "grid_metadata": {"units": "degree_C", "num_lats": 61, "num_lons": 91},
            "sst_grid": [28.5] * (61 * 91),
            "anom_grid": [0.5] * (61 * 91)
        }

        # Insert mock live document into memory store & Mongo (if active)
        db_manager.save_sst_daily(mock_live_doc)

        try:
            latest = db_manager.get_latest_sst()
            self.assertFalse(latest.get("is_seed"))
            self.assertIn(latest.get("data_source"), ["live", "cached", "cached (memory)"])
            print(f"\n[PASS] Live document resolution verified:\n  data_source: {latest.get('data_source')}\n  is_seed: {latest.get('is_seed')}")
        finally:
            # Clean up mock live document from memory store and Mongo
            if "sst_daily" in db_manager.memory_store:
                mem_key = f"ncdcOisst21NrtAgg_LonPM180_{now_str}_indian_ocean"
                db_manager.memory_store["sst_daily"].pop(mem_key, None)
            if db_manager.use_mongo and db_manager.db is not None:
                db_manager.db.sst_daily.delete_one({"date": now_str, "is_seed": False})

if __name__ == "__main__":
    unittest.main()
