#!/usr/bin/env python3
"""
Sagar Drishti — Standalone Live ERDDAP SST Ingestion, Backfill & Retention Runner
Designed for standalone execution (e.g. via GitHub Actions or Cron).

Key Capabilities:
1. Distributed MongoDB Lock (ingest_locks collection, default 30-min expiry with active renewal).
2. Backfill missing dates inside the retention window (up to MAX_BACKFILL_DAYS_PER_RUN, default 7).
3. Fetch & Validate NOAA OISST v2.1 grid data.
4. Retention Cleanup: Purges live sst_daily records older than RETENTION_WINDOW_DAYS (default 180).
5. Ingest Audit Trail: Records run status into ingest_runs collection.
"""

import os
import sys
import uuid
from typing import Tuple, Dict, Any, List, Optional
from datetime import datetime, timezone, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from erddap_client import fetch_and_transform_erddap_sst, get_erddap_latest_date, ERDDAP_DATASET_ID
from database import db_manager, MONGO_URI, get_db_name

RETENTION_WINDOW_DAYS = int(os.getenv("RETENTION_WINDOW_DAYS", "180"))
MAX_BACKFILL_DAYS_PER_RUN = int(os.getenv("MAX_BACKFILL_DAYS_PER_RUN", "7"))
LOCK_TTL_SECONDS = int(os.getenv("INGEST_LOCK_TTL_SECONDS", "1800"))  # Default 30 minutes

def acquire_distributed_lock(job_id: str) -> bool:
    """
    Acquires an expiry-based distributed lock in MongoDB 'ingest_locks' collection.
    Default expiry: 30 minutes (1800 seconds).
    Returns True if lock acquired, False if lock is held by another active run.
    """
    if not db_manager.use_mongo or db_manager.db is None:
        print("[LOCK INFO] Running in memory mode; skipping distributed Mongo lock.")
        return True

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=LOCK_TTL_SECONDS)

    lock_col = db_manager.db.ingest_locks
    existing_lock = lock_col.find_one({"_id": "ingest_lock"})

    if existing_lock:
        lock_expiry_str = existing_lock.get("expires_at")
        if lock_expiry_str:
            try:
                exp_dt = datetime.fromisoformat(lock_expiry_str.replace("Z", "+00:00"))
                if now < exp_dt:
                    print(f"[LOCK CONFLICT] Ingest lock currently held by job '{existing_lock.get('job_id')}' until {lock_expiry_str}.")
                    return False
            except Exception:
                pass

    # Upsert lock
    lock_doc = {
        "_id": "ingest_lock",
        "job_id": job_id,
        "acquired_at": now.isoformat(),
        "expires_at": expires_at.isoformat()
    }
    lock_col.update_one({"_id": "ingest_lock"}, {"$set": lock_doc}, upsert=True)
    print(f"[LOCK ACQUIRED] Distributed lock set for job '{job_id}' (expires at {expires_at.isoformat()}).")
    return True

def renew_distributed_lock(job_id: str):
    """Renews expiry duration for an active lock held by job_id during long runs."""
    if db_manager.use_mongo and db_manager.db is not None:
        try:
            new_expiry = (datetime.now(timezone.utc) + timedelta(seconds=LOCK_TTL_SECONDS)).isoformat()
            db_manager.db.ingest_locks.update_one(
                {"_id": "ingest_lock", "job_id": job_id},
                {"$set": {"expires_at": new_expiry}}
            )
            print(f"[LOCK RENEWED] Lock renewed for job '{job_id}' until {new_expiry}.")
        except Exception as ex:
            print(f"[LOCK RENEWAL WARNING] {ex}")

def release_distributed_lock(job_id: str):
    """Releases distributed lock if held by this job_id."""
    if db_manager.use_mongo and db_manager.db is not None:
        try:
            db_manager.db.ingest_locks.delete_one({"_id": "ingest_lock", "job_id": job_id})
            print(f"[LOCK RELEASED] Lock released for job '{job_id}'.")
        except Exception as ex:
            print(f"[LOCK RELEASE WARNING] Failed to release lock: {ex}")

def find_missing_dates(retention_days: int = 180, max_backfill: int = 7, max_date: Optional[str] = None) -> List[str]:
    """
    Identifies missing live SST dates within retention window up to max_backfill days, ending at max_date.
    Counts ONLY real live documents (is_seed: False, data_source: "live").
    """
    if max_date:
        try:
            start_dt = datetime.strptime(max_date, "%Y-%m-%d").date()
        except ValueError:
            start_dt = datetime.now(timezone.utc).date()
    else:
        start_dt = datetime.now(timezone.utc).date()

    candidate_dates = [(start_dt - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(retention_days)]

    existing_dates = set()
    if db_manager.use_mongo and db_manager.db is not None:
        try:
            existing_dates = set(db_manager.db.sst_daily.distinct("date", {"is_seed": False, "data_source": "live"}))
        except Exception:
            pass
    else:
        for v in db_manager.memory_store.get("sst_daily", {}).values():
            if not v.get("is_seed", False) and v.get("data_source") == "live" and "date" in v:
                existing_dates.add(v["date"])

    missing = [d for d in candidate_dates if d not in existing_dates]
    return missing[:max_backfill]

def clean_expired_live_sst(retention_days: int = 180) -> int:
    """
    Retention cleanup: Deletes LIVE sst_daily documents older than retention_days.
    NEVER touches seed_sst or other collections.
    Returns count of deleted documents.
    """
    cutoff_date = (datetime.now(timezone.utc) - timedelta(days=retention_days)).strftime("%Y-%m-%d")
    print(f"[RETENTION CLEANUP] Purging live sst_daily records older than {cutoff_date} ({retention_days}-day window)...")

    deleted_count = 0
    if db_manager.use_mongo and db_manager.db is not None:
        try:
            res = db_manager.db.sst_daily.delete_many({"is_seed": False, "date": {"$lt": cutoff_date}})
            deleted_count = res.deleted_count
            print(f"[RETENTION CLEANUP] Purged {deleted_count} expired live sst_daily records from MongoDB.")
        except Exception as ex:
            print(f"[RETENTION CLEANUP WARNING] Mongo error: {ex}")

    # Memory store cleanup
    mem_sst = db_manager.memory_store.get("sst_daily", {})
    keys_to_del = [k for k, v in mem_sst.items() if not v.get("is_seed", False) and v.get("date", "") < cutoff_date]
    for k in keys_to_del:
        mem_sst.pop(k, None)

    return deleted_count

def run_ingest_pipeline() -> Tuple[bool, str]:
    """
    Main ingestion & backfill workflow:
    1. Acquire distributed lock (30-min default expiry).
    2. Query ERDDAP for latest published date.
    3. Identify missing dates in retention window up to MAX_BACKFILL_DAYS_PER_RUN.
    4. Fetch, validate & store live SST records for missing dates (renewing lock per step).
    5. Run retention cleanup.
    6. Record audit run in ingest_runs.
    7. Release lock in finally block.
    """
    job_id = f"job-{uuid.uuid4().hex[:8]}"
    started_at = datetime.now(timezone.utc).isoformat()

    print("==================================================")
    print("   SAGAR DRISHTI — STANDALONE INGESTION PIPELINE  ")
    print("==================================================")
    print(f"Job ID          : {job_id}")
    print(f"Target Database : {get_db_name()}")
    print(f"Dataset ID      : {ERDDAP_DATASET_ID}")
    print(f"Retention Window: {RETENTION_WINDOW_DAYS} days")
    print(f"Max Backfill/Run: {MAX_BACKFILL_DAYS_PER_RUN} days")

    if not acquire_distributed_lock(job_id):
        skipped_run = {
            "job_id": job_id,
            "dataset_id": ERDDAP_DATASET_ID,
            "started_at": started_at,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "skipped",
            "rows_fetched": 0,
            "rows_accepted": 0,
            "rows_rejected": 0,
            "rejection_reasons": {},
            "error_message": "Job execution skipped: Distributed lock held by another active run.",
            "data_source": "none"
        }
        db_manager.record_ingest_run(skipped_run)
        print("[INGEST SKIPPED] Recorded skipped job in audit trail. Exiting code 0.")
        return True, "Job skipped due to active lock."

    dates_processed = 0
    dates_skipped_404 = 0
    real_failures = 0

    try:
        latest_published_date = get_erddap_latest_date()
        missing_dates = find_missing_dates(RETENTION_WINDOW_DAYS, MAX_BACKFILL_DAYS_PER_RUN, max_date=latest_published_date)
        print(f"[BACKFILL DISCOVERY] Target latest published date: {latest_published_date}")
        print(f"[BACKFILL DISCOVERY] Identified {len(missing_dates)} missing dates to fetch: {missing_dates}")

        # Default to latest if no missing dates found
        target_dates = missing_dates if missing_dates else [latest_published_date]

        for target_date in target_dates:
            renew_distributed_lock(job_id)
            doc, ingest_run = fetch_and_transform_erddap_sst(date_str=target_date)
            
            if doc is None and ingest_run is None:
                # HTTP 404: date not published
                print(f"[INGEST SKIPPED] Date {target_date or 'latest'} is not yet published on ERDDAP (HTTP 404).")
                dates_skipped_404 += 1
                continue

            run_dict = ingest_run.model_dump() if hasattr(ingest_run, 'model_dump') else ingest_run.dict()
            run_dict["job_id"] = job_id

            if doc is None:
                # Real failure (5xx, timeout, zero valid records)
                real_failures += 1
                db_manager.record_ingest_run(run_dict)
                print(f"[INGEST WARNING] Fetch failed for date: {target_date or 'latest'} (Status: {run_dict.get('status')})")
                continue

            doc_dict = doc.model_dump() if hasattr(doc, 'model_dump') else doc.dict()
            doc_dict["is_seed"] = False
            doc_dict["data_source"] = "live"
            msg = db_manager.save_sst_daily(doc_dict)
            dates_processed += 1

            run_dict["status"] = "success"
            run_dict["finished_at"] = datetime.now(timezone.utc).isoformat()
            db_manager.record_ingest_run(run_dict)
            print(f"[STORE SUCCESS] {msg} (Date: {doc_dict['date']})")

        # Run retention cleanup
        purged_count = clean_expired_live_sst(RETENTION_WINDOW_DAYS)

        if dates_processed > 0:
            overall_success = True
            summary_msg = f"Successfully processed {dates_processed} date(s)."
        elif real_failures == 0:
            overall_success = True
            summary_msg = f"All target dates up-to-date or not yet published (404 skipped: {dates_skipped_404})."
        else:
            overall_success = False
            summary_msg = f"Ingestion failed with {real_failures} real error(s)."

        print("--------------------------------------------------")
        print("LIVE INGESTION & RETENTION COMPLETED:")
        print(f"Dates Processed: {dates_processed}")
        print(f"Skipped (404)  : {dates_skipped_404}")
        print(f"Real Failures  : {real_failures}")
        print(f"Purged Expired : {purged_count} records (> {RETENTION_WINDOW_DAYS} days)")
        print("==================================================")
        return overall_success, summary_msg

    finally:
        release_distributed_lock(job_id)

def main():
    success, msg = run_ingest_pipeline()
    if not success:
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()
