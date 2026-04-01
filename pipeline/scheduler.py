"""
pipeline/scheduler.py
Background scheduler — runs fetch → transform → correlate every weekday at EOD.

FIX: Import all pipeline functions at module level (not inside run_pipeline).
     Lazy imports inside the scheduled function fail silently in background
     threads because sys.path is not guaranteed to be available.
"""
import sys
import os
import logging

# Ensure project root is always on path — needed for background thread context
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.events import EVENT_JOB_EXECUTED, EVENT_JOB_ERROR, EVENT_JOB_MISSED
from datetime import datetime

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE

# ── Import pipeline steps at MODULE LEVEL — NOT inside the function ───────────
# Lazy imports inside scheduled functions fail in background threads.
from pipeline.fetch     import run as fetch_run
from pipeline.transform import run as transform_run
from pipeline.correlate import run as correlate_run

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("scheduler")


def run_pipeline():
    """Full pipeline: fetch → transform → correlate."""
    start = datetime.now()
    logger.info(f"\n{'#'*50}")
    logger.info(f"  PIPELINE START  {start.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"{'#'*50}")
    try:
        logger.info("  Step 1/3 — FETCH")
        fetch_run()
        logger.info("  Step 2/3 — TRANSFORM")
        transform_run()
        logger.info("  Step 3/3 — CORRELATE")
        correlate_run()
        elapsed = (datetime.now() - start).seconds
        logger.info(f"  PIPELINE complete in {elapsed}s")
        return {"status": "success", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"  [PIPELINE ERROR] {e}", exc_info=True)
        return {"status": "error", "detail": str(e)}


def _scheduler_listener(event):
    if event.exception:
        logger.error(f"[SCHEDULER] Job FAILED: {event.job_id} — {event.exception}")
    elif hasattr(event, 'retval'):
        logger.info(f"[SCHEDULER] Job completed: {event.job_id}")
    else:
        logger.warning(f"[SCHEDULER] Job MISSED: {event.job_id}")


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(
        timezone="Asia/Kolkata",
        job_defaults={"coalesce": True, "max_instances": 1}
    )
    scheduler.add_job(
        func=run_pipeline,
        trigger=CronTrigger(
            day_of_week="mon-fri",
            hour=SCHEDULE_HOUR,
            minute=SCHEDULE_MINUTE,
            timezone="Asia/Kolkata"
        ),
        id="eod_pipeline",
        name="EOD Stock Pipeline",
        replace_existing=True,
    )
    scheduler.add_listener(
        _scheduler_listener,
        EVENT_JOB_EXECUTED | EVENT_JOB_ERROR | EVENT_JOB_MISSED
    )
    scheduler.start()
    jobs = scheduler.get_jobs()
    next_run = jobs[0].next_run_time if jobs else "unknown"
    logger.info(f"  [SCHEDULER] Started — Mon-Fri {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} IST")
    logger.info(f"  [SCHEDULER] Next run: {next_run}")
    return scheduler


if __name__ == "__main__":
    run_pipeline()