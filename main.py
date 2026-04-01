"""
main.py
App entry point. Run from project root:
    uvicorn main:app --reload

On startup:
  1. DB tables created
  2. If no data → runs full pipeline automatically (first-time setup)
  3. Background scheduler starts (EOD pipeline Mon-Fri 4 PM IST)

Dashboard: http://localhost:8000/dashboard/index.html
Swagger:   http://localhost:8000/docs
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config   import DASHBOARD_DIR
from database import init_db, get_latest_dates
from api.routes import router
from pipeline.scheduler import start_scheduler, run_pipeline


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ───────────────────────────────────────────────────────────────
    print("\n" + "="*50)
    print("  Pulse Stock Intelligence Dashboard")
    print("="*50)

    # 1. Ensure DB tables exist
    init_db()

    # 2. Auto-fetch on first run if DB is empty
    latest = get_latest_dates()
    if not latest:
        print("\n  No data found. Running initial pipeline (this takes ~3-5 min)...")
        run_pipeline()
    else:
        symbols = list(latest.keys())
        print(f"\n  Data found for: {symbols}")
        print(f"  Latest dates  : {latest}")

    # 3. Start background scheduler
    scheduler = start_scheduler()
    import main as _main
    _main._scheduler = scheduler   # store globally so /pipeline/scheduler can read it

    print(f"\n  Dashboard → http://localhost:8000/dashboard/index.html")
    print(f"  Swagger   → http://localhost:8000/docs")
    print("="*50 + "\n")

    yield

    # ── SHUTDOWN ──────────────────────────────────────────────────────────────
    scheduler.shutdown()
    print("  Scheduler stopped. Bye.")


# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(
    title="Pulse — Stock Intelligence Dashboard",
    description="NSE stock data pipeline with 10 technical indicators. Built for Pulse Internship.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API routes
app.include_router(router)

# Serve dashboard as static files → http://localhost:8000/dashboard/index.html
if os.path.exists(DASHBOARD_DIR):
    app.mount("/dashboard", StaticFiles(directory=DASHBOARD_DIR), name="dashboard")
    print(f"  Static: {DASHBOARD_DIR}")