"""
database.py
All DB operations in one place.
Every other file imports from here — nothing else touches SQLite directly.
"""
import pandas as pd
from sqlalchemy import create_engine, text
from config import DB_PATH


def get_engine():
    return create_engine(f"sqlite:///{DB_PATH}", echo=False)


def init_db():
    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS raw_prices (
                symbol      TEXT NOT NULL,
                date        TEXT NOT NULL,
                open        REAL,
                high        REAL,
                low         REAL,
                close       REAL,
                volume      INTEGER,
                fetched_at  TEXT,
                PRIMARY KEY (symbol, date)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS transformed_prices (
                symbol          TEXT NOT NULL,
                date            TEXT NOT NULL,
                open            REAL, high REAL, low REAL, close REAL,
                volume          INTEGER,
                daily_return    REAL,
                price_change    REAL,
                ma_7            REAL,
                ma_20           REAL,
                week52_high     REAL,
                week52_low      REAL,
                volatility_7    REAL,
                rsi_14          REAL,
                atr_14          REAL,
                beta_vs_nifty   REAL,
                PRIMARY KEY (symbol, date)
            )
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS correlation (
                symbol_1        TEXT NOT NULL,
                symbol_2        TEXT NOT NULL,
                correlation     REAL,
                computed_date   TEXT NOT NULL,
                PRIMARY KEY (symbol_1, symbol_2, computed_date)
            )
        """))
        conn.commit()
    print("[DB] Tables ready.")


# ── Write ─────────────────────────────────────────────────────────────────────
def save_raw(df: pd.DataFrame):
    df.to_sql("raw_prices", get_engine(), if_exists="append",
              index=False, method="multi", chunksize=500)

def save_transformed(df: pd.DataFrame):
    engine = get_engine()
    # delete existing rows for these symbols then re-insert (clean re-run)
    symbols = df["symbol"].unique().tolist()
    placeholders = ",".join([f"'{s}'" for s in symbols])
    with engine.connect() as conn:
        conn.execute(text(f"DELETE FROM transformed_prices WHERE symbol IN ({placeholders})"))
        conn.commit()
    df.to_sql("transformed_prices", engine, if_exists="append",
              index=False, method="multi", chunksize=500)

def save_correlation(df: pd.DataFrame):
    df.to_sql("correlation", get_engine(), if_exists="append",
              index=False, method="multi", chunksize=500)


# ── Read ──────────────────────────────────────────────────────────────────────
def get_latest_dates() -> dict:
    """Returns {symbol: latest_date} from raw_prices. Empty dict on first run."""
    try:
        df = pd.read_sql(
            "SELECT symbol, MAX(date) as latest FROM raw_prices GROUP BY symbol",
            get_engine()
        )
        return dict(zip(df["symbol"], df["latest"]))
    except Exception:
        return {}

def get_raw_all() -> pd.DataFrame:
    return pd.read_sql("SELECT * FROM raw_prices ORDER BY symbol, date", get_engine())

def get_transformed(symbol: str = None, days: int = None) -> pd.DataFrame:
    engine = get_engine()
    if symbol and days:
        df = pd.read_sql(f"""
            SELECT * FROM transformed_prices
            WHERE symbol = '{symbol.upper()}'
            ORDER BY date DESC LIMIT {days}
        """, engine)
        return df.sort_values("date").reset_index(drop=True)
    if symbol:
        return pd.read_sql(
            f"SELECT * FROM transformed_prices WHERE symbol = '{symbol.upper()}' ORDER BY date",
            engine
        )
    return pd.read_sql("SELECT * FROM transformed_prices ORDER BY symbol, date", engine)

def get_latest_price_per_symbol() -> pd.DataFrame:
    """Returns one row per symbol — the most recent close price. Used by sidebar."""
    return pd.read_sql("""
        SELECT t.symbol, t.date, t.close, t.daily_return, t.rsi_14
        FROM transformed_prices t
        INNER JOIN (
            SELECT symbol, MAX(date) as max_date
            FROM transformed_prices
            GROUP BY symbol
        ) latest ON t.symbol = latest.symbol AND t.date = latest.max_date
        ORDER BY t.symbol
    """, get_engine())

def get_correlation_latest() -> pd.DataFrame:
    try:
        return pd.read_sql("""
            SELECT * FROM correlation
            WHERE computed_date = (SELECT MAX(computed_date) FROM correlation)
        """, get_engine())
    except Exception:
        return pd.DataFrame()