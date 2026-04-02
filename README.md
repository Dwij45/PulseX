# 📈 PulseX — Stock Data Intelligence Dashboard

A stock market data platform.
Fetches real NSE data, computes technical indicators, serves them via a REST API,
and visualizes everything in an interactive dashboard — deployed live on Render.

**Live Demo:** https://pulsex-z311.onrender.com/dashboard/index.html
**API Docs (Swagger):** https://pulsex-z311.onrender.com/docs

---

## What This Does

- Pulls real NSE stock data using `yfinance` (daily OHLCV for 9 companies)
- Runs an **ELT pipeline**: Extract → Load raw data → Transform into computed features
- Stores everything in **SQLite** — raw prices in one table, computed features in another
- Computes **10 technical indicators** per stock per day (daily return, MA7, MA20, RSI-14, ATR-14, volatility, 52W high/low, Beta vs Nifty, price change)
- Computes a **cross-stock correlation matrix** across all 9 symbols
- Serves all data through a **FastAPI** REST layer with auto-generated Swagger docs
- Displays data in an interactive **Chart.js + custom canvas** dashboard
- Runs the pipeline **automatically every weekday at 4 PM IST** via APScheduler (after NSE market closes)
- Sends a **live push notification** to the browser when new data arrives (Server-Sent Events)
- Has a **manual Refresh button** on the dashboard for on-demand fetch

---

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.11 |
| Data Fetch | yfinance — mirrors NSE/BSE via Yahoo Finance |
| Data Processing | Pandas, NumPy |
| Database | SQLite via SQLAlchemy |
| API | FastAPI + Uvicorn |
| Scheduler | APScheduler (background cron job) |
| Frontend | HTML + CSS + Chart.js + Custom Canvas |
| Deployment | Render.com |

---

## Project Structure

```
PulseX/
├── main.py                  ← entry point — run this
├── config.py                ← all settings (DB path, schedule time, feature windows)
├── database.py              ← all DB read/write (nothing else touches SQLite)
├── requirements.txt
├── render.yaml
│
├── data/
│   ├── company_master.csv   ← 9 companies with sector tags
│   └── stocks.db            ← SQLite (auto-created on first run)
│
├── pipeline/
│   ├── fetch.py             ← Extract + Load: yfinance → raw_prices table
│   ├── transform.py         ← Compute all features → transformed_prices table
│   ├── correlate.py         ← Cross-stock correlation → correlation table
│   └── scheduler.py        ← Chains all 3 steps, runs daily at 4 PM IST
│
├── api/
│   └── routes.py            ← All FastAPI endpoints
│
└── dashboard/
    └── index.html           ← Frontend (served at /dashboard/index.html)
```

---

## Setup — Run Locally

```bash
git clone https://github.com/Dwij45/PulseX
cd PulseX

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux

pip install -r requirements.txt
uvicorn main:app --reload
```

On first run the app automatically fetches ~2 years of historical data for all companies (takes 2-4 minutes). After that it only fetches new dates incrementally.

Open:
- **Dashboard** → http://localhost:8000/dashboard/index.html
- **Swagger UI** → http://localhost:8000/docs

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/companies` | All companies. Filter: `?sector=IT` |
| GET | `/sectors` | All sector names |
| GET | `/sidebar` | Latest price + return for every symbol (used by sidebar) |
| GET | `/data/{symbol}` | Last N days OHLCV + all features. `?days=90` |
| GET | `/summary/{symbol}` | 52W high/low, RSI zone, Beta, volatility, avg close |
| GET | `/compare?symbol1=INFY&symbol2=TCS` | Side-by-side comparison |
| GET | `/correlation` | Full correlation matrix. `?sector=IT` |
| GET | `/top-movers` | Today's top gainers and losers |
| GET | `/pipeline/status` | Latest date per symbol in DB |
| POST | `/pipeline/run` | Manually trigger fetch → transform → correlate |
| GET | `/pipeline/events` | SSE stream — push notifications to dashboard |

All endpoints documented at `/docs` (Swagger UI).

---

## Features Computed

| Feature | What It Means |
|---|---|
| `daily_return` | (close - open) / open × 100 — % gain or loss for the day |
| `price_change` | close - previous close — absolute ₹ movement |
| `ma_7` | 7-day rolling average of close — short-term trend |
| `ma_20` | 20-day rolling average of close — medium-term trend |
| `week52_high` | Rolling max close over 252 trading days |
| `week52_low` | Rolling min close over 252 trading days |
| `volatility_7` | Std dev of daily_return over 7 days — risk measure |
| `rsi_14` | Relative Strength Index — above 70 overbought, below 30 oversold |
| `atr_14` | Average True Range — how much the stock moves per day in ₹ |
| `beta_vs_nifty` | 90-day rolling sensitivity to Nifty 50 market movement |

The **correlation matrix** shows how each pair of stocks moves together — computed from daily returns across all symbols and visualized as a color-coded heatmap.

---

## Companies Tracked

| Sector | Symbols |
|---|---|
| IT | INFY, TCS, WIPRO, HCLTECH, TECHM |
| Fintech | HDFCBANK, BAJAJFINSV, PAYTM |
| Conglomerate | RELIANCE |
| Benchmark | ^NSEI (Nifty 50 — used for Beta calculation only) |

Sectors chosen for their relevance to enterprise AI adoption — JarNox's core focus area.

---

## Dashboard Features

- **Sidebar** — all companies grouped by sector, showing latest close price and daily return %
- **Summary cards** — Price, Daily Return, 52W High, 52W Low, RSI (with overbought/oversold badge), Beta vs Nifty
- **Price chart** — toggle between Candlestick view and Line + MA7 + MA20 view
- **Volume bars** — green on positive days, red on negative days
- **RSI chart** — with reference lines at 70 and 30
- **Volatility chart** — 7-day rolling risk
- **Correlation heatmap** — full n×n matrix, red = positive, green = negative
- **Top Movers** — today's top 4 gainers and losers
- **Time filters** — 30D / 90D / 180D / 365D
- **Live ticker banner** — shows next auto-fetch countdown
- **Auto-refresh toast** — browser gets notified when scheduler completes, shows clickable "New data available" notification

---

## Data Pipeline — How It Works

```
NSE Market closes at 3:30 PM IST
           ↓
APScheduler fires at 4:00 PM IST (Mon-Fri)
           ↓
fetch.py   — checks last stored date per symbol
           — fetches only NEW dates from yfinance (incremental)
           — saves to raw_prices table
           ↓
transform.py — reads raw_prices
             — computes all 10 features per symbol
             — saves to transformed_prices table
           ↓
correlate.py — reads transformed_prices
             — computes pairwise correlation matrix
             — saves to correlation table
           ↓
SSE push — notifies connected browsers
         — toast appears: "New data available"
```

Running the pipeline twice on the same day does nothing — the `PRIMARY KEY (symbol, date)` constraint prevents duplicate rows.

---

## Production Notes

- **Data source in production**: yfinance (Yahoo Finance mirror of NSE). The official alternative is NSE Bhavcopy — an EOD CSV published daily at nseindia.com with no rate limits. Would use this for a production system.
- **Database**: SQLite is used here. For a multi-user production system, PostgreSQL would be the right choice.
- **Render free tier**: Disk resets on redeploy — stocks.db is rebuilt from scratch on startup. Data persists between restarts as long as there is no redeploy.
- **Cold start**: Render free tier spins down after inactivity — first request takes ~30 seconds to wake up. Normal for free tier.

---
