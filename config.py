"""
config.py
Single source of truth for all settings.
Change things here only — nothing else has hardcoded values.
"""
import os

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_DIR            = os.path.dirname(os.path.abspath(__file__))
DATA_DIR            = os.path.join(BASE_DIR, "data")
DB_PATH             = os.path.join(DATA_DIR, "stocks.db")
COMPANY_MASTER_PATH = os.path.join(DATA_DIR, "company_master.csv")
DASHBOARD_DIR       = os.path.join(BASE_DIR, "dashboard")

# ── Data fetch ────────────────────────────────────────────────────────────────
HISTORICAL_START    = "2023-01-01"

# ── Scheduler ─────────────────────────────────────────────────────────────────
SCHEDULE_HOUR       = 16        # 4:00 PM IST (after NSE market close 3:30 PM)
SCHEDULE_MINUTE     = 0

# ── Feature windows ───────────────────────────────────────────────────────────
MA_SHORT            = 7
MA_LONG             = 20
RSI_PERIOD          = 14
VOLATILITY_PERIOD   = 7
ATR_PERIOD          = 14
WEEK52_WINDOW       = 252
BETA_WINDOW         = 90