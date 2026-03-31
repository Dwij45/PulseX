"""
pipeline/correlate.py
Computes pairwise correlation matrix from daily_return.
Runs after transform each day.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from datetime import datetime
from database import get_transformed, save_correlation, get_correlation_latest


def run():
    print(f"\n{'='*50}\n  CORRELATE  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*50}")
    df = get_transformed()
    if df.empty:
        print("  [WARN] No transformed data. Run transform first.")
        return

    today = datetime.today().strftime("%Y-%m-%d")

    # Skip if already computed today
    existing = get_correlation_latest()
    if not existing.empty and existing["computed_date"].iloc[0] == today:
        print(f"  Correlation already computed for {today}. Skipping.")
        return

    df["date"] = pd.to_datetime(df["date"])
    pivot = df.pivot_table(index="date", columns="symbol", values="daily_return")
    pivot = pivot.dropna(thresh=30, axis=1)
    corr  = pivot.corr().round(4)

    records = []
    for s1 in corr.columns:
        for s2 in corr.columns:
            records.append({"symbol_1": s1, "symbol_2": s2,
                            "correlation": corr.loc[s1,s2], "computed_date": today})
    corr_df = pd.DataFrame(records)
    save_correlation(corr_df)
    print(f"  {len(corr.columns)}×{len(corr.columns)} matrix saved for {today}.\n  Correlate complete.")


if __name__ == "__main__":
    run()