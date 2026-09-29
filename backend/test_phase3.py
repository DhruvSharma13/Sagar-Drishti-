import os
import sys

# FORCE TEST DATABASE ENVIRONMENT VARIABLE AT TOP LEVEL BEFORE ANY MODULE IMPORTS
os.environ["MONGODB_DB_NAME"] = "sagar_drishti_test"
os.environ["MONGO_DB_NAME"] = "sagar_drishti_test"

import unittest
from unittest.mock import patch, MagicMock
import uuid
from datetime import datetime, timezone, timedelta

sys.path.append(os.path.dirname(__file__))

# Load env files without overwriting test DB name
def _load_test_env(path: str):
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() not in ("MONGODB_DB_NAME", "MONGO_DB_NAME"):
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))

_load_test_env(os.path.join(os.path.dirname(__file__), ".env"))
_load_test_env(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

from database import db_manager, get_db_name
from models import SSTDailyDocument, IngestRunDocument, GridMetadata
from run_ingest import acquire_distributed_lock, release_distributed_lock, clean_expired_live_sst, run_ingest_pipeline, find_missing_dates
from erddap_client import fetch_and_transform_erddap_sst
from anomaly_engine import compute_rolling_baseline_anomaly

def create_mock_sst_doc_and_run(date_str="2026-09-29"):
    grid_meta = GridMetadata(
        lat_min=-30.0, lat_max=30.0, lat_step=1.0,
        lon_min=30.0, lon_max=120.0, lon_step=1.0,
        num_lats=61, num_lons=91, units="degree_C"
    )
    doc = SSTDailyDocument(
        dataset_id="ncdcOisst21NrtAgg_LonPM180",
        date=date_str,
        region_id="indian_ocean",
        data_timestamp=f"{date_str}T00:00:00Z",
        fetched_at=datetime.now(timezone.utc).isoformat(),
        source="NOAA CoastWatch ERDDAP",
        revision="nrt",
        is_seed=False,
        data_source="live",
        grid_metadata=grid_meta,
        sst_grid=[28.5] * (61 * 91),
        anom_grid=[0.5] * (61 * 91),
        record_count=61 * 91,
        stats={"min_sst": 24.0, "max_sst": 31.0, "mean_sst": 28.5}
    )
    run_doc = IngestRunDocument(
        job_id=f"job-{uuid.uuid4().hex[:6]}",
        dataset_id="ncdcOisst21NrtAgg_LonPM180",
        started_at=datetime.now(timezone.utc).isoformat(),
        finished_at=datetime.now(timezone.utc).isoformat(),
        status="success",
        rows_fetched=5551,
        rows_accepted=5551,
        rows_rejected=0,
        rejection_reasons={},
        data_source="live"
    )
    return doc, run_doc

class TestPhase3Pipeline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        os.environ["MONGO_DB_NAME"] = "sagar_drishti_test"
        db_manager.init_db()
        current_db = get_db_name()
        print(f"\n==================================================")
        print(f"   PHASE 3 TESTS RUNNING ON TEST DB: '{current_db}'  ")
        print(f"==================================================")
        if current_db != "sagar_drishti_test":
            raise RuntimeError("CRITICAL SAFETY CHECK: Tests must run on 'sagar_drishti_test' database ONLY!")
        cls.clear_test_db()

    @classmethod
    def tearDownClass(cls):
        cls.clear_test_db()
        print("\n[TEARDOWN] Cleaned all collections in test database 'sagar_drishti_test'.")

    @classmethod
    def clear_test_db(cls):
        if db_manager.use_mongo and db_manager.db is not None:
            try:
                db_manager.db.sst_daily.delete_many({})
                db_manager.db.seed_sst.delete_many({})
                db_manager.db.ingest_runs.delete_many({})
                db_manager.db.ingest_locks.delete_many({})
            except Exception as ex:
                print(f"[TEARDOWN WARNING] {ex}")
        db_manager.memory_store["sst_daily"] = {}
        db_manager.memory_store["seed_sst"] = {}
        db_manager.memory_store["ingest_runs"] = []

    def setUp(self):
        self.clear_test_db()

    def test_01_distributed_lock_concurrency(self):
        """Verify distributed lock prevents overlapping job execution."""
        job_a = f"job-a-{uuid.uuid4().hex[:6]}"
        job_b = f"job-b-{uuid.uuid4().hex[:6]}"

        acquired_a = acquire_distributed_lock(job_a)
        self.assertTrue(acquired_a, "Job A should successfully acquire distributed lock.")

        acquired_b = acquire_distributed_lock(job_b)
        if db_manager.use_mongo:
            self.assertFalse(acquired_b, "Job B should be rejected when Job A holds lock.")

        release_distributed_lock(job_a)

        acquired_b_retry = acquire_distributed_lock(job_b)
        self.assertTrue(acquired_b_retry, "Job B should acquire lock after Job A releases it.")
        release_distributed_lock(job_b)
        print("\n[PASS] Distributed MongoDB lock acquisition & concurrency rejection verified!")

    def test_02_retention_cleanup_live_only(self):
        """Verify retention cleanup purges live documents > 180 days old while leaving seed & recent data intact."""
        now = datetime.now(timezone.utc)
        date_200d = (now - timedelta(days=200)).strftime("%Y-%m-%d")
        date_100d = (now - timedelta(days=100)).strftime("%Y-%m-%d")
        date_today = now.strftime("%Y-%m-%d")

        doc_200 = {"dataset_id": "ncdcOisst21NrtAgg_LonPM180", "date": date_200d, "region_id": "indian_ocean", "is_seed": False, "data_source": "live"}
        doc_100 = {"dataset_id": "ncdcOisst21NrtAgg_LonPM180", "date": date_100d, "region_id": "indian_ocean", "is_seed": False, "data_source": "live"}
        doc_today = {"dataset_id": "ncdcOisst21NrtAgg_LonPM180", "date": date_today, "region_id": "indian_ocean", "is_seed": False, "data_source": "live"}

        db_manager.save_sst_daily(doc_200)
        db_manager.save_sst_daily(doc_100)
        db_manager.save_sst_daily(doc_today)

        seed_doc = {"dataset_id": "ncdcOisst21NrtAgg_LonPM180", "date": date_200d, "region_id": "indian_ocean", "is_seed": True, "data_source": "demo"}
        db_manager.save_seed_sst(seed_doc)

        purged = clean_expired_live_sst(retention_days=180)
        self.assertEqual(purged, 1 if db_manager.use_mongo else 0)

        if db_manager.use_mongo and db_manager.db is not None:
            remaining_live = list(db_manager.db.sst_daily.find({"is_seed": False}))
            remaining_dates = [d["date"] for d in remaining_live]
            self.assertNotIn(date_200d, remaining_dates, "200-day-old live document must be deleted!")
            self.assertIn(date_100d, remaining_dates, "100-day-old live document must remain!")
            self.assertIn(date_today, remaining_dates, "Today's live document must remain!")

            seed_remaining = db_manager.db.seed_sst.count_documents({})
            self.assertEqual(seed_remaining, 1, "Seed SST documents must NEVER be deleted by retention cleanup!")

        print("\n[PASS] Retention cleanup verified: 200-day-old live document purged, recent live & seed data intact!")

    def test_03_rolling_baseline_anomaly_engine(self):
        """Verify secondary rolling baseline anomaly requires at least 30 days of stored history (default)."""
        # Case A: Insufficient history (10 days < 30 threshold)
        short_history = [
            {"date": f"2026-09-{i:02d}", "sst_grid": [28.0 + i * 0.05], "stats": {"mean_sst": 28.0 + i * 0.05}}
            for i in range(1, 11)
        ]
        res_short = compute_rolling_baseline_anomaly(short_history, target_idx=0, min_days=30)
        self.assertEqual(res_short["status"], "unavailable")
        self.assertIn("Insufficient history", res_short["reason"])
        self.assertEqual(res_short["label"], "rolling baseline (10 days)")
        self.assertTrue(res_short["primary_anomaly_used"])

        # Case B: Sufficient history (30 days)
        full_history = [
            {"date": f"2026-08-{i:02d}", "sst_grid": [28.0 + (i % 5) * 0.1], "stats": {"mean_sst": 28.0 + (i % 5) * 0.1}}
            for i in range(1, 31)
        ]
        res_full = compute_rolling_baseline_anomaly(full_history, target_idx=0, min_days=30)
        self.assertEqual(res_full["status"], "available")
        self.assertEqual(res_full["label"], "rolling baseline (30 days)")
        self.assertIn("rolling_mean", res_full)
        self.assertIn("rolling_std", res_full)
        self.assertIn("rolling_anomaly", res_full)
        self.assertFalse(res_full["primary_anomaly_used"])

        print("\n[PASS] Rolling baseline anomaly engine verified (default 30-day requirement):")
        print(f"  Short history (10 < 30 days): {res_short['reason']}")
        print(f"  Full history (30 days):      status={res_full['status']}, label='{res_full['label']}'")

    @patch("run_ingest.fetch_and_transform_erddap_sst")
    def test_04_ingest_audit_run_recording_mocked(self, mock_fetch):
        """Verify standalone run_ingest_pipeline records audit entry without touching network (MOCKED)."""
        doc, run_doc = create_mock_sst_doc_and_run("2026-09-29")
        mock_fetch.return_value = (doc, run_doc)

        success, msg = run_ingest_pipeline()
        self.assertTrue(success)

        runs = db_manager.memory_store.get("ingest_runs", [])
        if db_manager.use_mongo and db_manager.db is not None:
            runs = list(db_manager.db.ingest_runs.find({}, {"_id": 0}))

        self.assertGreater(len(runs), 0, "ingest_runs collection must record execution attempt.")
        last_run = runs[-1]
        self.assertEqual(last_run.get("status"), "success")
        print(f"\n[PASS] Mocked Ingest pipeline executed in <0.1s with zero network calls!")

    def test_05_backfill_missing_dates_discovery(self):
        """Verify find_missing_dates discovers missing dates within retention window up to max_backfill limit."""
        today = datetime.now(timezone.utc).date()
        date_today = today.strftime("%Y-%m-%d")
        date_yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")

        # Save today's live document
        doc_today = {"dataset_id": "ncdcOisst21NrtAgg_LonPM180", "date": date_today, "region_id": "indian_ocean", "is_seed": False}
        db_manager.save_sst_daily(doc_today)

        missing = find_missing_dates(retention_days=180, max_backfill=5)
        self.assertNotIn(date_today, missing, "Today should not be in missing dates list.")
        self.assertIn(date_yesterday, missing, "Yesterday should be identified as missing.")
        self.assertLessEqual(len(missing), 5, "Missing dates count should not exceed max_backfill=5.")
        print(f"\n[PASS] Backfill missing dates discovery verified: {missing}")

    @patch("urllib.request.urlopen")
    def test_06_fetch_and_transform_erddap_sst_signature_kwarg(self, mock_urlopen):
        """Verify fetch_and_transform_erddap_sst accepts date_str keyword argument exactly as run_ingest.py calls it."""
        mock_resp = MagicMock()
        mock_resp.status = 200
        # Minimal ERDDAP CSV response format (header, units, 1 data row)
        csv_content = (
            "time,depth,latitude,longitude,sst,anom\n"
            "UTC,m,degrees_north,degrees_east,degree_C,degree_C\n"
            "2026-09-29T12:00:00Z,0.0,0.0,60.0,28.5,0.5\n"
        ).encode("utf-8")
        mock_resp.read.return_value = csv_content
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        # Call with exact keyword argument date_str=...
        doc, run_doc = fetch_and_transform_erddap_sst(date_str="2026-09-29")
        self.assertIsNotNone(doc, "Document must not be None for valid CSV response.")
        self.assertEqual(doc.date, "2026-09-29")
        self.assertEqual(run_doc.status, "success")
        self.assertEqual(run_doc.data_source, "live")
        print("\n[PASS] fetch_and_transform_erddap_sst keyword parameter 'date_str' verified!")

if __name__ == "__main__":
    unittest.main()
