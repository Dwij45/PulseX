"""
pipeline/scheduler.py
Background scheduler — runs fetch → transform → correlate every weekday at EOD.
Also exposes run_pipeline() which the API calls for manual trigger.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime

from config import SCHEDULE_HOUR, SCHEDULE_MINUTE


def run_pipeline():
    """Full pipeline: fetch → transform → correlate. Called by scheduler + manual trigger."""
    from pipeline.fetch     import run as fetch_run
    from pipeline.transform import run as transform_run
    from pipeline.correlate import run as correlate_run

    print(f"\n{'#'*50}\n  PIPELINE RUN  {datetime.now()}\n{'#'*50}")
    try:
        fetch_run()
        transform_run()
        correlate_run()
        print(f"\n  PIPELINE complete at {datetime.now()}\n")
        return {"status": "success", "timestamp": datetime.now().isoformat()}
    except Exception as e:
        print(f"\n  [PIPELINE ERROR] {e}\n")
        return {"status": "error", "detail": str(e)}


def start_scheduler() -> BackgroundScheduler:
    scheduler = BackgroundScheduler(timezone="Asia/Kolkata")
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
    scheduler.start()
    print(f"  [SCHEDULER] EOD pipeline — Mon-Fri {SCHEDULE_HOUR:02d}:{SCHEDULE_MINUTE:02d} IST")
    return scheduler


if __name__ == "__main__":
    run_pipeline()