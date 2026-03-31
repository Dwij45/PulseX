"""
pipeline/transform.py
TRANSFORM step — reads raw_prices, computes all features, writes transformed_prices.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from datetime import datetime

from config   import MA_SHORT, MA_LONG, RSI_PERIOD, VOLATILITY_PERIOD, ATR_PERIOD, WEEK52_WINDOW, BETA_WINDOW
from database import get_raw_all, save_transformed


def add_daily_return(df):
    df["daily_return"] = ((df["close"] - df["open"]) / df["open"] * 100).round(4)
    return df

def add_price_change(df):
    df["price_change"] = (df["close"] - df["close"].shift(1)).round(4)
    return df

def add_moving_averages(df):
    df["ma_7"]  = df["close"].rolling(MA_SHORT).mean().round(4)
    df["ma_20"] = df["close"].rolling(MA_LONG).mean().round(4)
    return df

def add_52_week(df):
    df["week52_high"] = df["close"].rolling(WEEK52_WINDOW, min_periods=1).max().round(4)
    df["week52_low"]  = df["close"].rolling(WEEK52_WINDOW, min_periods=1).min().round(4)
    return df

def add_volatility(df):
    df["volatility_7"] = df["daily_return"].rolling(VOLATILITY_PERIOD).std().round(4)
    return df

def add_rsi(df):
    delta    = df["close"].diff()
    gain     = delta.clip(lower=0)
    loss     = -delta.clip(upper=0)
    avg_gain = gain.rolling(RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    avg_loss = loss.rolling(RSI_PERIOD, min_periods=RSI_PERIOD).mean()
    rs       = avg_gain / avg_loss.replace(0, np.nan)
    df["rsi_14"] = (100 - (100 / (1 + rs))).round(2)
    return df

def add_atr(df):
    prev   = df["close"].shift(1)
    tr     = pd.concat([df["high"]-df["low"],
                        (df["high"]-prev).abs(),
                        (df["low"]-prev).abs()], axis=1).max(axis=1)
    df["atr_14"] = tr.rolling(ATR_PERIOD).mean().round(4)
    return df

def add_beta(df, nifty_returns):
    if nifty_returns is None:
        df["beta_vs_nifty"] = None
        return df
    stock_ret = df.set_index("date")["daily_return"]
    aligned   = pd.concat([stock_ret, nifty_returns], axis=1, join="inner").dropna()
    aligned.columns = ["stock","nifty"]
    betas = []
    for i in range(len(aligned)):
        w = aligned.iloc[max(0, i-BETA_WINDOW+1): i+1]
        if len(w) < 10:
            betas.append(np.nan)
        else:
            cov = np.cov(w["stock"], w["nifty"])
            var = np.var(w["nifty"])
            betas.append(round(cov[0][1]/var, 4) if var != 0 else np.nan)
    beta_s = pd.Series(betas, index=aligned.index, name="beta_vs_nifty")
    df = df.set_index("date")
    df["beta_vs_nifty"] = beta_s
    return df.reset_index()


def run():
    print(f"\n{'='*50}\n  TRANSFORM  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")
    raw_df = get_raw_all()
    if raw_df.empty:
        print("  [WARN] No raw data. Run fetch first.")
        return

    raw_df["date"] = pd.to_datetime(raw_df["date"])

    # Nifty for beta
    nifty_returns = None
    if "NSEI" in raw_df["symbol"].unique():
        nifty = raw_df[raw_df["symbol"]=="NSEI"][["date","close"]].sort_values("date").copy()
        nifty["nifty_return"] = (nifty["close"].diff() / nifty["close"].shift(1) * 100)
        nifty_returns = nifty.set_index("date")["nifty_return"]
        print("  Nifty data found — computing Beta.")

    symbols = [s for s in raw_df["symbol"].unique() if s != "NSEI"]
    results = []

    for symbol in symbols:
        df = raw_df[raw_df["symbol"]==symbol].copy().sort_values("date").reset_index(drop=True)
        df = add_daily_return(df)
        df = add_price_change(df)
        df = add_moving_averages(df)
        df = add_52_week(df)
        df = add_volatility(df)
        df = add_rsi(df)
        df = add_atr(df)
        df = add_beta(df, nifty_returns)
        results.append(df)
        print(f"  [OK]  {symbol}: {len(df)} rows")

    final = pd.concat(results, ignore_index=True)
    final = final[["symbol","date","open","high","low","close","volume",
                   "daily_return","price_change","ma_7","ma_20",
                   "week52_high","week52_low","volatility_7","rsi_14","atr_14","beta_vs_nifty"]].copy()
    final["date"] = pd.to_datetime(final["date"]).dt.strftime("%Y-%m-%d")
    final = final.where(pd.notnull(final), None)

    save_transformed(final)
    print(f"\n  {len(final)} rows saved to transformed_prices.\n  Transform complete.")


if __name__ == "__main__":
    run()