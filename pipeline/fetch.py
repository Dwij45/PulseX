"""
pipeline/fetch.py
EXTRACT + LOAD step.
First run  → fetches HISTORICAL_START to today for all symbols.
Later runs → incremental, only new dates per symbol.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

from config   import COMPANY_MASTER_PATH, HISTORICAL_START
from database import init_db, save_raw, get_latest_dates


def fetch_single(nse_symbol: str, start: str, end: str) -> pd.DataFrame | None:
    try:
        raw = yf.download(nse_symbol, start=start, end=end,
                          interval="1d", auto_adjust=True, progress=False)
        if raw.empty:
            return None
        if isinstance(raw.columns, pd.MultiIndex):
            raw.columns = raw.columns.droplevel(1)
        raw.reset_index(inplace=True)
        raw = raw[["Date","Open","High","Low","Close","Volume"]].copy()
        raw.rename(columns={"Date":"date","Open":"open","High":"high",
                             "Low":"low","Close":"close","Volume":"volume"}, inplace=True)
        raw["symbol"]     = nse_symbol.replace(".NS","").replace(".BO","")
        raw["fetched_at"] = datetime.now().isoformat()
        raw = raw[["symbol","date","open","high","low","close","volume","fetched_at"]]
        raw["date"]   = pd.to_datetime(raw["date"], errors="coerce")
        raw["open"]   = pd.to_numeric(raw["open"],   errors="coerce").round(4)
        raw["high"]   = pd.to_numeric(raw["high"],   errors="coerce").round(4)
        raw["low"]    = pd.to_numeric(raw["low"],    errors="coerce").round(4)
        raw["close"]  = pd.to_numeric(raw["close"],  errors="coerce").round(4)
        raw["volume"] = pd.to_numeric(raw["volume"], errors="coerce").fillna(0).astype(int)
        raw.dropna(subset=["date","close"], inplace=True)
        raw["date"] = raw["date"].dt.strftime("%Y-%m-%d")
        return raw
    except Exception as e:
        print(f"  [ERROR] {nse_symbol}: {e}")
        return None


def run():
    print(f"\n{'='*50}\n  FETCH  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")
    init_db()
    companies    = pd.read_csv(COMPANY_MASTER_PATH)
    latest_map   = get_latest_dates()
    today        = datetime.today().strftime("%Y-%m-%d")
    # today        = "2024-01-01"
    total_new    = 0

    for _, row in companies.iterrows():
        symbol, nse_symbol = row["symbol"], row["nse_symbol"]
        if symbol in latest_map and latest_map[symbol]:
            start = (datetime.strptime(latest_map[symbol], "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
            if start >= today:
                print(f"  [SKIP] {symbol} — up to date ({latest_map[symbol]})")
                continue
        else:
            start = HISTORICAL_START

        print(f"  Fetching {symbol} ({nse_symbol})  {start} → {today}")
        df = fetch_single(nse_symbol, start, today)
        if df is None or df.empty:
            print(f"  [WARN] No data for {symbol}")
            continue
        save_raw(df)
        total_new += len(df)
        print(f"  [OK]   {symbol}: +{len(df)} rows")

    print(f"\n  Total new rows: {total_new}\n  Fetch complete.")


if __name__ == "__main__":
    run()