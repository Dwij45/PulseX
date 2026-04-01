"""
api/routes.py
All FastAPI endpoints. Imported by main.py.
"""
import asyncio
import json
import pandas as pd
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from database import (
    get_transformed, get_latest_price_per_symbol,
    get_correlation_latest, get_latest_dates
)
from config import COMPANY_MASTER_PATH

router = APIRouter()


# ── SSE broadcast state ───────────────────────────────────────────────────────
# One asyncio.Queue per connected browser tab.
# scheduler.py calls notify_pipeline_complete() when pipeline finishes,
# which drops a message into every queue → every browser gets the push.
_sse_clients: set = set()

def notify_pipeline_complete(status: dict):
    """
    Called by run_pipeline() after pipeline finishes.
    Puts a message into every connected browser's queue.
    Dead / full queues are removed automatically.
    """
    payload = json.dumps({"event": "pipeline_complete", **status})
    dead = set()
    for q in _sse_clients:
        try:
            q.put_nowait(payload)
        except asyncio.QueueFull:
            dead.add(q)        # browser is not reading — drop it
    _sse_clients.difference_update(dead)


# ── Helpers ───────────────────────────────────────────────────────────────────
def load_companies() -> pd.DataFrame:
    return pd.read_csv(COMPANY_MASTER_PATH)

def to_json(df: pd.DataFrame) -> list:
    return df.where(pd.notnull(df), None).to_dict(orient="records")

def safe_float(val, decimals=2):
    if val is None: return None
    try:
        f = float(val)
        return None if pd.isna(f) else round(f, decimals)
    except Exception:
        return None


# ── Health ────────────────────────────────────────────────────────────────────
@router.get("/", tags=["Health"])
def root():
    return {"status": "ok", "message": "JarNox Stock Intelligence API"}


# ── Companies ─────────────────────────────────────────────────────────────────
@router.get("/companies", tags=["Companies"])
def get_companies(sector: str = Query(default=None)):
    """All companies. Filter: ?sector=IT"""
    df = load_companies()
    if sector:
        df = df[df["sector"].str.upper() == sector.upper()]
        if df.empty:
            raise HTTPException(404, f"No companies for sector '{sector}'")
    return to_json(df)


@router.get("/sectors", tags=["Companies"])
def get_sectors():
    return {"sectors": sorted(load_companies()["sector"].unique().tolist())}


@router.get("/sidebar", tags=["Companies"])
def get_sidebar():
    """
    Returns latest price + daily_return + rsi for every symbol.
    Used by sidebar — one row per company, no history, fast query.
    """
    df = get_latest_price_per_symbol()
    if df.empty:
        raise HTTPException(404, "No data. Run the pipeline first.")
    companies = load_companies()[["symbol","full_name","sector"]]
    merged = companies.merge(df, on="symbol", how="left")
    return to_json(merged)


# ── Stock Data ────────────────────────────────────────────────────────────────
@router.get("/data/{symbol}", tags=["Stock Data"])
def get_stock_data(
    symbol: str,
    days: int = Query(default=30, ge=1, le=365)
):
    """Last N days OHLCV + all features. Default 30. Use ?days=90"""
    df = get_transformed(symbol=symbol.upper(), days=days)
    if df.empty:
        raise HTTPException(404, f"No data for '{symbol.upper()}'. Run the pipeline.")
    return to_json(df)


@router.get("/summary/{symbol}", tags=["Stock Data"])
def get_summary(symbol: str):
    """Summary card: latest price, 52W high/low, RSI zone, beta, volatility."""
    symbol = symbol.upper()
    df = get_transformed(symbol=symbol)
    if df.empty:
        raise HTTPException(404, f"No data for '{symbol}'")

    df["date"] = pd.to_datetime(df["date"])
    latest = df.sort_values("date").iloc[-1]
    rsi    = safe_float(latest.get("rsi_14"), 2)
    zone   = ("overbought" if rsi and rsi >= 70
               else "oversold" if rsi and rsi <= 30
               else "neutral")

    return {
        "symbol":              symbol,
        "latest_date":         str(latest["date"].date()),
        "latest_close":        safe_float(latest["close"]),
        "latest_daily_return": safe_float(latest.get("daily_return"), 4),
        "price_change":        safe_float(latest.get("price_change")),
        "week52_high":         safe_float(df["close"].max()),
        "week52_low":          safe_float(df["close"].min()),
        "avg_close":           safe_float(df["close"].mean()),
        "latest_rsi":          rsi,
        "rsi_zone":            zone,
        "avg_volatility":      safe_float(df["volatility_7"].mean(), 4),
        "latest_atr":          safe_float(latest.get("atr_14")),
        "beta_vs_nifty":       safe_float(latest.get("beta_vs_nifty"), 4),
        "total_rows":          len(df),
    }


# ── Compare ───────────────────────────────────────────────────────────────────
@router.get("/compare", tags=["Analysis"])
def compare_stocks(
    symbol1: str = Query(...),
    symbol2: str = Query(...)
):
    """Side-by-side comparison. /compare?symbol1=INFY&symbol2=TCS"""
    result = {}
    for sym in [symbol1.upper(), symbol2.upper()]:
        df = get_transformed(symbol=sym)
        if df.empty:
            raise HTTPException(404, f"No data for '{sym}'")
        latest = df.sort_values("date").iloc[-1]
        result[sym] = {
            "latest_close":      safe_float(latest["close"]),
            "avg_daily_return":  safe_float(df["daily_return"].mean(), 4),
            "week52_high":       safe_float(df["close"].max()),
            "week52_low":        safe_float(df["close"].min()),
            "avg_volatility":    safe_float(df["volatility_7"].mean(), 4),
            "latest_rsi":        safe_float(latest.get("rsi_14")),
            "latest_atr":        safe_float(latest.get("atr_14")),
            "beta_vs_nifty":     safe_float(latest.get("beta_vs_nifty"), 4),
        }
    return result


# ── Correlation ───────────────────────────────────────────────────────────────
@router.get("/correlation", tags=["Analysis"])
def get_correlation(sector: str = Query(default=None)):
    """Full correlation matrix. Filter: ?sector=IT"""
    df = get_correlation_latest()
    if df.empty:
        raise HTTPException(404, "No correlation data. Run pipeline first.")
    if sector:
        syms = load_companies()[
            load_companies()["sector"].str.upper() == sector.upper()
        ]["symbol"].tolist()
        df = df[df["symbol_1"].isin(syms) & df["symbol_2"].isin(syms)]
    pivot = {}
    for _, row in df.iterrows():
        s1, s2 = row["symbol_1"], row["symbol_2"]
        if s1 not in pivot: pivot[s1] = {}
        pivot[s1][s2] = safe_float(row["correlation"], 4)
    return {"correlation_matrix": pivot,
            "computed_date": df["computed_date"].iloc[0] if len(df) else "—"}


# ── Top Movers ────────────────────────────────────────────────────────────────
@router.get("/top-movers", tags=["Analysis"])
def get_top_movers(n: int = Query(default=4, ge=1, le=10)):
    """Top N gainers and losers by daily_return on latest date."""
    df = get_transformed()
    if df.empty:
        raise HTTPException(404, "No data available.")
    df["date"] = pd.to_datetime(df["date"])
    latest_date = df["date"].max()
    day = df[df["date"]==latest_date][["symbol","close","daily_return"]].copy()
    day = day.dropna(subset=["daily_return"]).sort_values("daily_return", ascending=False)
    return {
        "date":    str(latest_date.date()),
        "gainers": to_json(day.head(n)),
        "losers":  to_json(day.tail(n).iloc[::-1]),
    }


# ── Pipeline status ───────────────────────────────────────────────────────────
@router.get("/pipeline/status", tags=["Pipeline"])
def pipeline_status():
    """Shows latest date per symbol in DB — tells you when data was last fetched."""
    latest = get_latest_dates()
    if not latest:
        return {"status": "empty", "message": "No data in DB. Trigger a pipeline run."}
    return {"status": "ok", "latest_dates": latest}


# ── Manual pipeline trigger ───────────────────────────────────────────────────
@router.post("/pipeline/run", tags=["Pipeline"])
def trigger_pipeline():
    """
    Manually triggers fetch → transform → correlate.
    Called by the Refresh button on the dashboard.
    Runs in foreground — response comes back when complete (~2-5 min first run).
    """
    from pipeline.scheduler import run_pipeline
    result = run_pipeline()
    if result["status"] == "error":
        raise HTTPException(500, result["detail"])
    return result


# ── Scheduler info ────────────────────────────────────────────────────────────
@router.get("/pipeline/scheduler", tags=["Pipeline"])
def scheduler_info():
    """
    Shows scheduler status and next scheduled run time.
    Use this to verify the scheduler is alive and registered correctly.
    """
    from pipeline.scheduler import start_scheduler
    from apscheduler.schedulers.background import BackgroundScheduler
    # Access the global scheduler stored on app state
    import main as _main
    sched = getattr(_main, '_scheduler', None)
    if sched is None:
        return {"status": "unknown", "message": "Scheduler reference not found"}
    jobs = sched.get_jobs()
    if not jobs:
        return {"status": "no_jobs", "message": "Scheduler running but no jobs registered"}
    job = jobs[0]
    return {
        "status":        "running",
        "job_id":        job.id,
        "job_name":      job.name,
        "next_run_IST":  str(job.next_run_time),
        "trigger":       str(job.trigger),
        "scheduler_state": str(sched.state),
    }


# ── SSE — Server-Sent Events ──────────────────────────────────────────────────
@router.get("/events", tags=["SSE"])
async def sse_stream():
    """
    Persistent connection. Browser connects once on page load and stays connected.
    When pipeline finishes, notify_pipeline_complete() puts a message in this
    browser's queue → generator() picks it up → sends to browser → page reloads.

    Keep-alive ping every 25s prevents Nginx / proxy from killing idle connections
    on deployment (Render, Railway, etc).
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=10)
    _sse_clients.add(queue)

    async def generator():
        try:
            while True:
                try:
                    # Block here until a message arrives or 25s timeout
                    msg = await asyncio.wait_for(queue.get(), timeout=25)
                    yield f"data: {msg}\n\n"
                except asyncio.TimeoutError:
                    # No pipeline event — send a keep-alive comment
                    # Browser ignores lines starting with ":" — it just resets proxy timers
                    yield ": keep-alive\n\n"
        except asyncio.CancelledError:
            # Browser closed the tab — FastAPI cancels this generator
            pass
        finally:
            # Always clean up — prevents memory leak from dead connections
            _sse_clients.discard(queue)

    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering": "no",   # disables Nginx response buffering on deployment
        }
    )