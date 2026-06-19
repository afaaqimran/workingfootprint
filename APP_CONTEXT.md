# Afaaqs Foot Print Server — Application Context Document

This document provides a complete reference for any AI system or developer working on this application.

**Table of Contents:**
- [Quick Summary](#quick-summary) — What the app does and key tech
- [Features Checklist](#features-checklist) — All implemented features
- [Overview](#overview) — Application details
- [Getting Started](#getting-started-quick-reference) — Setup instructions
- [Repository Status](#repository-status) — Git and GitHub info
- [File Structure](#file-structure) — Directory layout
- [Authentication](#authentication) — Analytics token setup
- [Flask Routes](#flask-routes) — All API endpoints
- [Frontend UI](#frontend-ui-charthtml) — All 9 tabs explained
- [Time-Based Analysis](#time-based-analysis-tba--detailed-calculation-guide) — TBA calculations
- [Common Tasks](#common-tasks--troubleshooting) — How-tos
- [Known Limitations](#known-limitations--workarounds) — Issues and fixes
- [Dependencies](#dependencies-requirements_upstoxxt) — Python packages

---

## Quick Summary

**What it does:** Real-time Indian stock market analysis platform specialized in NIFTY options. Displays live candlestick footprint charts, options premiums, volatility analysis, and time-based market snapshots via Upstox WebSocket + REST APIs.

**Key UI tabs:** Chart (futures footprint) • Options Chain • Straddle • OI Tracker • Volatility Skew • Full Option Chain • Rate of Change • Options Footprint (ATM locked) • Time-Based Analysis

**Data sources:** Upstox WebSocket v3 (market ticks), Upstox REST APIs (PCR, Max Pain), SQLite (historical candles/footprints)

**Tech stack:** Python 3, Flask, Socket.IO, Lightweight Charts.js, Chart.js

**Deployment:** Vultr VPS (Ubuntu) + Gunicorn with eventlet async, systemd service, auto login/logout cron

---

## Features Checklist

| Feature | Status | Notes |
|---------|--------|-------|
| Live futures footprint chart (NIFTY/BANKNIFTY) | ✅ Complete | 1/3/5/15 min TF, buy/sell volume overlay |
| Options chain with 3 trigger signals (T1/T2/T3) | ✅ Complete | ITM premiums, SMA crossover, OI decline detection |
| Straddle premium tracker | ✅ Complete | Live chart with zoom/pan, spike alerts |
| OI tracker with change % (5m/10m/15m/30m) | ✅ Complete | Per-strike OI + volume analysis |
| Volatility Skew (IV via Black-Scholes Newton-Raphson) | ✅ Complete | CE/PE IV curves, >20% amber highlighting |
| Full Option Chain (CE/PE paired by strike) | ✅ Complete | OI highlighting, ITM/OTM coloring |
| Rate of Change (RoC %) — rolling & fixed modes | ✅ Complete | 30s/1m/3m windows, per option |
| Options Footprint Chart (ATM CE/PE locked) | ✅ Complete | Multi-strike selection, 7 offsets (ATM ±300/±200/±100), real-time updates for all offsets, dropdown with actual strike prices, current day data only |
| NIFTY Option Chain Time-Based Analysis | ✅ Complete | 5-min snapshots, 11 columns, PCR/Max Pain from APIs, auto-capture at 09:18 on login |
| India VIX subscription & display | ✅ Complete | Real-time ticker in TBA header |
| ATM strike locking (options footprint only) | ✅ Complete | Login-time lock, unaffected by spot movement |
| Top 3 OI highlighting with gradients | ✅ Complete | Option chain CE/PE columns |
| Green/Red arrows for metric changes | ✅ Complete | PCR, IV, VIX, Max Pain, Fut OI Chg |
| Footprint alert bell (Web Audio API) | ✅ Complete | Volume threshold, per-level deduplication |
| Auto login/logout cron | ✅ Complete | 9:13 AM / 3:31 PM IST weekdays |
| CSV export (TBA snapshots) | ✅ Complete | Downloadable date-stamped file |
| Database per-symbol routing | ✅ Complete | NIFTY.db, BANKNIFTY.db, OPTIONS_ATM.db |
| 180-day data retention | ✅ Complete | Auto cleanup on startup |
| Responsive tab switching | ✅ Complete | Main controls hidden except on Chart tab |

---

## Overview

**Application Name:** Afaaqs Foot Print Server  
**Purpose:** Real-time NIFTY/BANKNIFTY futures footprint chart with options chain, straddle premium tracking, OI tracker, volatility skew chart, full option chain, ATM options footprint chart, and NIFTY Option Chain Time-Based Analysis — powered by Upstox WebSocket market data and Upstox REST APIs.  
**Server:** Vultr VPS — IP `65.20.75.231`  
**Port:** `5002` (firewall open)  
**URL:** `http://65.20.75.231:5002`

---

## Server & Deployment

| Item | Detail |
|------|--------|
| OS | Linux (Ubuntu) |
| App directory | `/opt/finalfootprint` |
| Python venv | `/opt/finalfootprint/venv` |
| WSGI server | Gunicorn with eventlet worker, 1 worker |
| systemd service | `finalfootprint.service` |
| Service file | `/etc/systemd/system/finalfootprint.service` |
| Start/stop | `systemctl start/stop/restart finalfootprint` |
| Logs | `journalctl -u finalfootprint -f` |
| Firewall | UFW — ports 22, 5001, 5002 open |

**Service definition:**
```
WorkingDirectory=/opt/finalfootprint
ExecStart=/opt/finalfootprint/venv/bin/gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5002 footprint_web_app_upstox:app
Restart=always
```

---

## Getting Started (Quick Reference)

### For Local Development
```bash
cd /Users/afaaqimran/advancedfootprint/finalfootprint/finalfootprint
python3 -m venv venv
source venv/bin/activate
pip install -r requirements_upstox.txt
python footprint_web_app_upstox.py
# Open http://localhost:5000 in browser and click Login
```

### For Production (Vultr VPS)
```bash
# SSH to VPS
ssh root@65.20.75.231

# Manage service
systemctl start/stop/restart finalfootprint
systemctl status finalfootprint

# View logs
journalctl -u finalfootprint -f

# Deploy changes
cd /opt/finalfootprint
git pull origin main
systemctl restart finalfootprint
```

### Key Files to Edit
| File | Purpose |
|------|---------|
| `footprint_web_app_upstox.py` | All backend routes, APIs, state management |
| `templates/chart.html` | All UI tabs, JavaScript logic, styling |
| `requirements_upstox.txt` | Python dependencies |

---

## Repository Status

| Item | Detail |
|------|--------|
| Primary repo | `https://github.com/afaaqimran/finalfootprint.git` |
| Backup repo | `https://github.com/afaaqimran/Footprintandoptiontrigger.git` |
| Active branch | `main` |
| Default branch | `main` (merged from `feature/options-chain-websocket-stability`) |
| GitHub PAT | Stored in git remote URL (use `git remote -v` to check) |
| Clone command | `git clone https://<PAT>@github.com/afaaqimran/finalfootprint.git` |

**To push to backup:**
```bash
cd /opt/finalfootprint
git add -A
git commit -m "your message"
git push backup main
```

**Current git status (local dev):**
```
M  APP_CONTEXT.md              (documentation updates)
M  footprint_web_app_upstox.py (backend with all features)
M  templates/chart.html        (frontend with all tabs)
?? .vscode/                    (IDE config, not committed)
?? footprint_data_*.db         (SQLite DBs, not committed)
```

---



## File Structure

```
/opt/finalfootprint/
├── footprint_web_app_upstox.py     # Main Flask app — all routes, data processing, WebSocket logic
├── upstox_websocket_v3.py          # Upstox WebSocket client with auto-reconnect
├── instrument_manager.py           # Downloads/caches Upstox instrument master (futures contracts)
├── MarketDataFeed_pb2.py           # Protobuf decoder for Upstox market data feed
├── MarketDataFeed_pb2_grpc.py      # gRPC stub (unused but required by protobuf)
├── auto_session.sh                 # Cron script for auto login/logout
├── requirements_upstox.txt         # Python dependencies
├── footprint_data_NIFTY.db         # SQLite DB — NIFTY 1-min candle + footprint data
├── footprint_data_OPTIONS_ATM.db   # SQLite DB — ATM CE and PE options 1-min candle + footprint data
├── footprint_data.db               # SQLite DB — default/fallback DB
├── instruments_cache.json          # Cached Upstox instrument master (refreshed every 24h)
├── footprint.service               # Original service file (reference only)
├── templates/
│   ├── chart.html                  # Main chart UI (footprint + options chain + straddle + OI tracker + volatility skew + full option chain + options footprint chart + time-based analysis tabs)
│   └── login_upstox.html           # Login page
```

---

## Authentication

**Method:** Upstox Analytics Token (long-lived, no daily OAuth required)  
**Token validity:** 1 year — expires **21 March 2027**  
**Token location:** Hardcoded as `ANALYTICS_TOKEN` constant in `footprint_web_app_upstox.py`  
**Expiry reminder:** App shows a warning on login starting 10 days before expiry (from 11 Mar 2027)  
**To regenerate:** Go to [https://account.upstox.com/developer/apps#analytics](https://account.upstox.com/developer/apps#analytics) → Analytics tab → Generate Token

**API credentials (pre-configured, hidden in login page):**
- API Key: `cdf3628c-aced-4d3e-b079-10a89f96be5c`
- API Secret: `ezbpksdbmk`

**Login flow:**
1. User opens `http://65.20.75.231:5002`
2. Clicks "Login" — no token input needed
3. Backend verifies analytics token against `/v3/feed/market-data-feed/authorize`
4. Session created with `user_id = 'analytics_user'`
5. WebSocket starts, futures + options subscriptions begin

---

## Auto Login/Logout (Cron)

The app auto-logs in at market open and logs out at market close, Monday–Friday.

| Action | IST | UTC (cron schedule) |
|--------|-----|---------------------|
| Login  | 9:13 AM | `43 3 * * 1-5` |
| Logout | 3:31 PM | `1 10 * * 1-5` |

**Script:** `/opt/finalfootprint/auto_session.sh login|logout`  
**Log:** `/var/log/footprint_session.log`  
**Session cookie:** `/opt/finalfootprint/.session_cookie`

---

## Data Flow

```
Upstox WebSocket v3 (wss)
        │
        ▼
UpstoxWebSocketV3 (upstox_websocket_v3.py)
  - Auto-reconnect with exponential backoff
  - Sends binary JSON subscription messages
  - Decodes Protobuf responses (MarketDataFeed_pb2)
        │
        ▼
process_websocket_data() in footprint_web_app_upstox.py
  ├── NSE_INDEX|Nifty 50  → nifty_spot_ltp (for ATM calculation + TBA spot)
  ├── NSE_INDEX|India VIX → vix_ltp (for TBA VIX column)
  ├── Options keys        → options_cache {ltp, atp, ohlc, volume, oi}
  │                       → oi_history {(timestamp_ms, oi)} rolling 35-min window
  │                       → if key == atm_fp_ce_key → _process_atm_option_footprint('CE')
  │                       → if key == atm_fp_pe_key → _process_atm_option_footprint('PE')
  └── Futures token       → OHLC candle + footprint processing
        │
        ├── FootprintProcessor.process_intrabar_footprint()
        │     - Classifies volume as buy/sell (price vs open)
        │     - Rounds to tick size (0.25)
        │     - Enforces lot size rounding
        │
        ├── DataStorage.store_candle() → SQLite (always as 1-min)
        │
        ├── socketio.emit('ohlc_data') → browser via Socket.IO (futures chart)
        │
        └── socketio.emit('options_fp_data') → browser via Socket.IO (options footprint chart)

Upstox REST APIs (called at each TBA snapshot, every 5 min during market hours)
  ├── GET /v2/market/pcr      → PCR column
  └── GET /v2/market/max-pain → Max Pain column
```

---

## WebSocket Subscriptions

On login, the app subscribes to:
1. **Futures instrument** — default NIFTY front-month (e.g. `NSE_FO|37054`), mode `full`
2. **NIFTY 50 spot index** — `NSE_INDEX|Nifty 50`, mode `ltpc`
3. **India VIX** — `NSE_INDEX|India VIX`, mode `ltpc` — used by the Time-Based Analysis tab
4. **NIFTY options** — 13 strikes (ATM-300 to ATM+300), both CE and PE, mode `full`

**ATM Monitor thread** — runs every 10 seconds, re-subscribes options if ATM strike shifts by 50 pts (with 15pt hysteresis buffer). Has a 30-second cooldown between re-subscriptions and waits up to 30s for NIFTY spot on startup to prevent rapid-fire re-subscription loops.

---

## Database

| DB file | Contents |
|---------|----------|
| `footprint_data_NIFTY.db` | NIFTY 1-min candles + footprint levels |
| `footprint_data_BANKNIFTY.db` | BANKNIFTY (created on first BANKNIFTY data) |
| `footprint_data_OPTIONS_ATM.db` | ATM CE (`NIFTY_CE_ATM`) and PE (`NIFTY_PE_ATM`) 1-min option candles + footprint levels. Locked to login-time ATM strike for the entire day. |
| `footprint_data.db` | Default fallback |

**Tables (all databases share the same schema):**
- `candles` — timestamp, symbol, open, high, low, close, ltp, volume, volume_diff, timeframe
- `footprint_levels` — candle_timestamp, symbol, price, buy_qty, sell_qty, total_qty, timeframe

**Retention:** 180 days. Old data cleaned on startup.  
**Storage:** Always stored as 1-min. Higher timeframes resampled in-memory at query time via `resample_data()`.

---

## Flask Routes

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Chart page (requires auth) or login page |
| `/login` | POST | Authenticate using analytics token |
| `/logout` | GET | Disconnect WebSocket, clear session |
| `/api/current-user` | GET | Check session status |
| `/api/user-symbols` | GET | Get available futures contracts (NIFTY/BANKNIFTY) |
| `/api/stored-data` | GET | Historical candle + footprint data (params: symbol, timeframe, days) |
| `/api/live-data` | GET | Latest live data snapshot |
| `/api/change-instrument` | POST | Switch futures instrument + lot size |
| `/api/change-timeframe` | POST | Switch chart timeframe |
| `/api/options-chain` | GET | NIFTY options chain from WebSocket cache, includes T2 (SMA) and T3 (OI trend) signals |
| `/api/straddle` | GET | Straddle premiums (CE+PE) per strike |
| `/api/oi-tracker` | GET | OI + OI change % (5m/10m/15m/30m) for all subscribed options |
| `/api/volatility-skew` | GET | Implied volatility per strike computed via Black-Scholes (Newton-Raphson solver) |
| `/api/option-chain-full` | GET | Full option chain paired by strike — CE left, PE right, with OI, OHLC, LTP |
| `/api/roc` | GET | Rate of change % of option LTP over 30s/1m/3m — rolling or fixed mode (`?mode=rolling\|fixed`) |
| `/api/options-footprint-data` | GET | Historical ATM CE/PE option candle + footprint data from `footprint_data_OPTIONS_ATM.db` (params: type=CE\|PE, days) |
| `/api/tba-snapshot` | GET | Single Time-Based Analysis snapshot — Nifty Spot, PCR (Upstox API), Put/Call OI, IV, VIX, Support/Resistance, Max Pain (Upstox API), Futures OI Change %, Bias |

---

## Frontend UI (chart.html)

Nine tabs on the left vertical sidebar:
### 📈 Chart Tab
- Lightweight Charts candlestick chart
- Footprint canvas overlay (buy/sell volume at each price level)
- Timeframe selector (1/3/5/15 min)
- Symbol selector (NIFTY/BANKNIFTY futures)
- Buy Qty / Sell Qty / Trace / Alert threshold filters — **specific to the futures footprint chart only**
  - Default Buy Qty: 20000
  - Default Sell Qty: 20000
  - **Default Trace: 10000** (filters out footprint boxes with volume below this threshold)
- Draw lines tool
- Historical data loaded on login via `/api/stored-data`
- Live updates via Socket.IO `ohlc_data` event
- X-axis shows date + time in IST (`dd Mon, HH:MM`)
- Chart height: `calc(100vh - 36px)` to avoid tab bar overlap
- **The main controls toolbar (symbol selector, TF buttons, filters) is hidden when the Options Footprint tab is active**

### ⚡ Options Chain Tab
- NIFTY ATM/ITM options table
- Columns: Type, Strike, Label, ATP, LTP, ATP-LTP, Open, High, Low, Volume, T1, T2, T3
- Auto-refreshes every 2 seconds from WebSocket cache
- **Trigger 1 logic** — fires on an ITM option when ALL 3 conditions are met:
  1. Option is ITM (CE strike < ATM, or PE strike > ATM)
  2. LTP < ATP (trading below average price)
  3. `|ATP - LTP|` of this ITM row < `|ATP - LTP|` of the ATM row (same type)
  - Interpretation: ITM option is showing less discount to its average than ATM — signals relative strength/directional intent
- **Trigger 2 logic** — SMA crossover on NIFTY futures closes, **per option type**:
  - Queries last 8 completed 1-min candle closes from SQLite (excludes current open candle)
  - `SMA5 = avg of last 5 closes`, `SMA8 = avg of last 8 closes`
  - **CE rows:** T2 fires when `SMA5 > SMA8` (uptrend favours calls)
  - **PE rows:** T2 fires when `SMA5 < SMA8` (downtrend favours puts)
  - Shows ✅ badge (teal) on ITM rows when condition met, muted text on OTM
  - Shows ⏳ until 8 candles have accumulated (~8 min after login)
  - SMA5, SMA8 values and current trend shown in the header bar
- **Trigger 3 logic** — OI decreasing per strike:
  - Compares current OI against OI from 2 ticks ago using `oi_history`
  - `oi_now < oi_2_ticks_ago` → 📉 OI ↓ badge (red) — position unwinding detected
  - `oi_now >= oi_2_ticks_ago` → OI ↑ muted text
  - Shows ⏳ until at least 3 OI ticks have arrived
- **All-Triggers Log** — displayed below the table, inside the same scrollable panel:
  - Logs an entry only when **T1 + T2 + T3 all fire simultaneously** on the same row
  - Columns: Time (IST) | Strike | CE/PE | LTP
  - Deduplication: same strike+type logs only once per minute
  - Most recent entry at top, keeps last 50 entries
  - Clear button to wipe the log manually

### 🎯 Straddle Tab
- Header: NIFTY Spot, ATM strike, Expiry, Lowest straddle, Day Low/High
- Strike table: ±350 pts around lowest premium strike, columns: Strike | CE LTP | PE LTP | Straddle
- Lowest premium strike highlighted with 🎯
- Live premium chart (Chart.js line chart) with Y-axis on both left and right sides
  - Y-axis (both sides) auto-syncs to actual premium range via `afterUpdate` plugin hook
  - Zoom/pan via scroll wheel, pinch, drag (x-axis only)
  - Reset Zoom button — resets view and re-enables auto-fit on live updates
  - Chart updates live without requiring Reset Zoom on login
- Premium spike alerts at 50%, 75%, 100% rise from day low
- Auto-refreshes every 2 seconds

### 📊 OI Tracker Tab
- Two side-by-side tables: CALL Options (CE) and PUT Options (PE)
- Header: NIFTY Spot, ATM Strike, Expiry, last update time
- Columns per table: Strike | LTP | OI | Volume | 5m % | 10m % | 15m % | 30m %
- ATM row highlighted in teal with `◀` marker
- OI change % colored green (increase) / red (decrease) / grey (no data yet)
- OI change % cells with `|change| >= 30%` get a pulsing highlight — teal background for +30%, red for -30%
- OI change % shows `—` until sufficient history has accumulated for that interval
- Auto-refreshes every 5 seconds from WebSocket cache + `oi_history`
- Data sourced from the existing options WebSocket subscription (mode `full`) — no additional subscriptions needed

### 📉 Volatility Skew Tab
- Header: NIFTY Spot, ATM, Expiry, DTE (days to expiry)
- Chart.js line chart plotting CE IV (teal) and PE IV (red) across all subscribed strikes
- Dashed ATM vertical line via `chartjs-plugin-annotation`
- IV computed server-side using Black-Scholes with Newton-Raphson solver (100 iterations, 0.001 precision)
- Risk-free rate: 6.5% (India 10yr approx). IV cells turn amber when IV > 20%
- Two IV tables below the chart: CE strikes (left) and PE strikes (right)
- ATM row highlighted with `◀` marker
- Auto-refreshes every 5 seconds while tab is active

### 🔗 Option Chain Tab
- Full NIFTY weekly option chain — CE on the left, Strike in the centre, PE on the right
- Columns (CE side): OI | LTP | Open | High | Close | Low
- Columns (PE side): LTP | Open | High | Close | Low | OI
- ITM/OTM row highlighting:
  - CE ITM rows (strike < ATM): subtle teal cell tint
  - PE ITM rows (strike > ATM): subtle red/pink cell tint
  - OTM rows: near-invisible grey tint
  - ATM row: amber background, bold text, `◀` marker
- Highest OI cell on each side highlighted in gold/amber with bold text
- LTP colored green if above open, red if below
- High column green, Low column red across both sides
- OI values formatted as `1.2L`, `3.4Cr` for readability
- Auto-scrolls to ATM row on first load
- Auto-refreshes every 3 seconds while tab is active

### ⚡️ Rate of Change Tab
- Two side-by-side tables: CALL (CE) and PUT (PE)
- Header: NIFTY Spot, ATM, Expiry, mode dropdown
- Columns per table: Strike | LTP | 30s % | 1m % | 3m %
- **Two modes via dropdown:**
  - **Rolling (sliding window):** `RoC % = ((ltp_now - ltp_T_ago) / ltp_T_ago) × 100` — always shows change vs exactly T seconds ago, updates every tick
  - **Fixed (candle reset):** `RoC % = ((ltp_now - ltp_at_period_start) / ltp_at_period_start) × 100` — resets at each 30s/1m/3m boundary, like a candle
- Green for positive, red for negative; bold when `|RoC| ≥ 5%`; background highlight when `|RoC| ≥ 10%`
- Shows `—` until sufficient `ltp_history` has accumulated for each window
- Auto-refreshes every 3 seconds while tab is active
- Data sourced from `ltp_history` (per instrument key, rolling 5-min window recorded on every options tick)

### 🕯 Options Footprint Chart Tab
- **Multi-Strike Selection:** Users can now view and switch between 7 different strike offsets in addition to the locked ATM
  - Dropdown selector shows actual strike prices (e.g., 24200, 24300, 24400 instead of generic labels)
  - 7 available offsets: ATM-300, ATM-200, ATM-100, ATM, ATM+100, ATM+200, ATM+300
  - ATM strike is **locked at login time** — computed from NIFTY spot at the moment of first options subscription, then fixed for the entire trading day
  - Selection persists when switching between offsets
  
- **Real-Time Updates for All Offsets:**
  - All 14 strike/type combinations (7 offsets × CE/PE) subscribe to WebSocket and receive real-time ticks
  - Charts update instantly as new candles form for the selected offset
  - Data for all 14 combinations stored in database (`footprint_data_OPTIONS_ATM.db`)
  - When offset changed, charts load current-day data and display with real-time updates
  
- **Side-by-side Candlestick + Footprint Charts:**
  - Left half: **CALL (CE)** contract for selected offset
  - Right half: **PUT (PE)** contract for selected offset
  - Each chart shows locked ATM reference and selected offset actual strike
  
- **Independent Toolbar** (separate from futures chart controls):
  - **Strike Dropdown:** Select from 7 offset options with actual strike prices
  - Spot price display (live, updates every 5 seconds)
  - Current strike info (locked ATM and selected offset)
  - TF buttons: 1m / 3m / 5m / 15m (client-side resampling of 1-min stored data)
  - **Footprint toggle** — starts ON by default
  - **Buy ≥** filter — hides buy boxes below threshold
  - **Sell ≥** filter — hides sell boxes below threshold
  - **Trace ≥** filter — hides all boxes (buy or sell) below threshold
  
- **Data Sources:**
  - Historical data loaded from `footprint_data_OPTIONS_ATM.db` per offset via `/api/options-footprint-data?offset={value}`
  - Current day only (no historical date range)
  - Live updates via Socket.IO `options_fp_data` event with offset field
  - All 14 combinations processed automatically regardless of UI selection
  
- **Canvas Footprint Overlay:**
  - Buy volume boxes: right side, teal border
  - Sell volume boxes: left side, red border
  - Footprint volume uses raw contract count (no lot-size flooring)
  
- **Time Display:**
  - LightweightCharts IST time offset (+19800s) applied for accurate market timestamps

### ⏱ NIFTY Option Chain Time-Based Analysis Tab
- **Auto-capture on login:** TBA snapshot capture automatically starts at 09:18 IST (or first `:X3/:X8` boundary after market open) immediately after user login, without requiring manual action
- Captures a structured snapshot every **5 minutes** aligned to IST clock boundaries: **09:18, 09:23, 09:28 ... 15:28, 15:33**
  - First slot is 09:18 — the first `:X3/:X8` boundary after market open (09:15)
  - Countdown timer in the header shows time until next auto-snapshot
  - Before 09:15 → shows "Market opens at 09:15 IST"; after 15:30 → shows "Market closed"
- Manual **📸 Capture Now** button available at any time to force an immediate snapshot
- **🗑 Clear** button wipes all rows; **⬇ CSV** exports the full table as a downloadable CSV file
- Rows displayed newest-at-top; latest row highlighted in amber; alternating row backgrounds

**Columns and how each is calculated:**

| Column | Source | Calculation |
|--------|--------|-------------|
| **Time** | Server IST clock | `HH:MM` at moment of snapshot |
| **Nifty Spot** | `nifty_spot_ltp` WebSocket | Live NIFTY 50 index LTP; ▲/▼ arrow vs previous row computed client-side |
| **PCR** | Upstox REST API `GET /v2/market/pcr` | `data.insights[-1].pcr` (latest 5-min bucket). Falls back to `data.pcr` (overall day), then to local `total PE OI ÷ total CE OI` across 13 subscribed strikes if API fails |
| **Put OI (ATM & -1)** | `options_cache` WebSocket | OI + volume label for ATM PE and ATM-50 PE. Volume label: High (≥1.5× ATM vol), Moderate (≥0.8×), Low |
| **Call OI (ATM & +1)** | `options_cache` WebSocket | OI + volume label for ATM CE and ATM+50 CE |
| **IV** | Black-Scholes Newton-Raphson (server) | Average of ATM CE IV and ATM PE IV. Same solver as Volatility Skew tab. `S`=spot, `K`=ATM, `T`=DTE/365, `r`=6.5% |
| **VIX** | `vix_ltp` WebSocket | Live India VIX from `NSE_INDEX\|India VIX` subscription |
| **Support / Resistance** | `options_cache` + `oi_history` | Highest PE OI strike = Support, highest CE OI strike = Resistance. Status: **Holding** if OI ≥ OI 2 ticks ago, **Under Pressure** if OI declining |
| **Max Pain** | Upstox REST API `GET /v2/market/max-pain` | `data.insights[-1].max_pain` (latest 5-min bucket). Falls back to `data.max_pain` (overall day), then to local computation across 13 subscribed strikes |
| **Fut OI Chg** | SQLite futures DB | `(latest VTT − previous VTT) / previous VTT × 100` from last 2 rows of `candles` table |
| **Bias** | PCR heuristic | PCR ≥ 1.4 → Strong Bullish; 1.15–1.4 → Bullish; 0.85–1.15 → Neutral; 0.65–0.85 → Bearish; < 0.65 → Strong Bearish. Nudged one step bearish if spot is within 75pts of support strike that is Under Pressure |

**Upstox REST API calls (made at each snapshot):**

| API | Endpoint | Params |
|-----|----------|--------|
| PCR | `GET https://api.upstox.com/v2/market/pcr` | `instrument_key=NSE_INDEX\|Nifty 50`, `expiry=YYYY-MM-DD`, `date=today`, `bucket_interval=5` |
| Max Pain | `GET https://api.upstox.com/v2/market/max-pain` | same params |

Both use the existing `ANALYTICS_TOKEN` for authorisation. Expiry is auto-converted from `'05 Jun 2026'` → `'2026-06-05'`. A `⚠️` log entry is printed if the API returns an unexpected response; a `ℹ️` log entry is printed when the local fallback is used.

**Limitation:** Support/Resistance, IV, and volume labels use only the 13 near-ATM subscribed strikes (ATM ± 300 pts). PCR and Max Pain come from the full Upstox chain via their APIs.

---

## Footprint Alert

- Alert threshold input in the chart toolbar — set a buy/sell qty value
- 🔔 On / 🔕 Off toggle button — alert is off by default, must be enabled manually
- Fires a **bell sound** (Web Audio API — two sine oscillators at 880 Hz + 2200 Hz with exponential decay) once per unique price level per candle
- Tracks fired levels via `alertFiredLevels` Set — resets when candle timestamp changes
- Turning off the toggle immediately stops any playing sound via `stopAlert()`

---

## OI Tracker — Backend Detail

**Data source:** `fullFeed.marketFF.oi` field from Upstox WebSocket v3 `full` mode feed.

**`options_cache`** (per instrument key) includes:
```python
{
    'ltp':    float,   # Last traded price
    'cp':     float,   # Close price (prev day)
    'atp':    float,   # Average traded price
    'volume': int,     # Volume traded today (VTT)
    'open':   float,   # Day open
    'high':   float,   # Day high
    'low':    float,   # Day low
    'oi':     int,     # Open interest
    'ts':     int,     # Timestamp ms
}
```

**`oi_history`** (per instrument key):
- List of `(timestamp_ms, oi)` tuples
- Appended on every tick where `oi > 0`
- Rolling 35-minute window (older entries pruned automatically)
- Used by `/api/oi-tracker` to compute OI change % for 5m/10m/15m/30m intervals
- Used by `/api/options-chain` Trigger 3 to detect OI declining (compares last vs 2-ticks-ago)

**`ltp_history`** (per instrument key):
- List of `(timestamp_ms, ltp)` tuples
- Appended on every options tick where `ltp > 0`
- Rolling 5-minute window
- Used by `/api/roc` to compute % change over 30s/1m/3m windows

**`nifty_history`**:
- List of `(timestamp_ms, spot)` tuples for NIFTY spot price
- Rolling 5-minute window
- Previously used for NIFTY-normalised RoC (now unused but retained)

---

## Volatility Skew — Backend Detail

**Route:** `/api/volatility-skew`  
**Method:** Black-Scholes with Newton-Raphson IV solver  
- Uses `ltp` from `options_cache` as market price input  
- `S` = NIFTY spot, `K` = strike, `T` = DTE / 365, `r` = 0.065  
- 100 Newton-Raphson iterations, convergence threshold 0.001  
- Returns `None` for strikes where LTP is zero or below intrinsic value  
- IV capped at 0–500% range to filter solver divergence  

---

## Time-Based Analysis (TBA) — Detailed Calculation Guide

### Capture Schedule
- **Market hours:** 09:15 AM – 3:30 PM IST (Monday–Friday)
- **First snapshot:** 09:18 IST (first `:X3` or `:X8` boundary after market open 09:15)
- **Recurring snapshots:** Every 5 minutes thereafter (09:23, 09:28, 09:33 ... 15:28, 15:33)
- **Outside hours:** Header shows "Market opens at 09:15 IST" (before) or "Market closed" (after 3:30 PM)
- **Manual capture:** 📸 button allows capture anytime, no restriction

### Per-Column Calculation Details

| Column | Data Source | Calculation | Arrows | Color Logic |
|--------|-------------|-------------|--------|------------|
| **Time** | Server IST clock | `now.strftime('%H:%M')` | — | Amber on latest row |
| **Nifty Spot** | WebSocket `NSE_INDEX\|Nifty 50` | Live LTP | ▲/▼ vs prev row | Green up / Red down |
| **PCR** | REST API → Upstox `/v2/market/pcr?bucket_interval=5` | `insights[-1].pcr` (latest 5-min); fallback `data.pcr` → local calc | ▲ Green / ▼ Red | Teal ≥1.3, Cyan ≥1.0, Amber ≥0.8, Red <0.8 |
| **Put OI (ATM & -1)** | WebSocket options_cache | Two rows: ATM PE strike + (ATM-50) PE strike, each with OI + volume label | — | Vol label color: Green (High), Amber (Moderate), Grey (Low) |
| **Call OI (ATM & +1)** | WebSocket options_cache | Two rows: ATM CE strike + (ATM+50) CE strike, each with OI + volume label | — | Vol label color: Green (High), Amber (Moderate), Grey (Low) |
| **IV** | Black-Scholes Newton-Raphson solver | Average of `(IV_CE_ATM + IV_PE_ATM) / 2` | ▲ Red / ▼ Green (higher IV = more uncertainty) | Amber if >20%, else white |
| **VIX** | WebSocket `NSE_INDEX\|India VIX` | Live LTP | ▲ Red / ▼ Green (higher VIX = fear/volatility) | Red if >20, Amber if >15, else white |
| **Support / Resistance** | WebSocket options_cache + oi_history | Support = highest PE OI strike + status. Resistance = highest CE OI strike + status. Status = "Holding" if current OI ≥ OI from 2 ticks ago, else "Under Pressure" | — | Green Support / Red Resistance text |
| **Max Pain** | REST API → Upstox `/v2/market/max-pain?bucket_interval=5` | `insights[-1].max_pain` (latest 5-min); fallback `data.max_pain` → local brute-force calc | ▲/▼ Grey (directionally neutral) | Amber text |
| **Fut OI Chg %** | SQLite futures DB `candles` table | `(OI_now - OI_prev) / OI_prev × 100` from last 2 1-min candle rows | ▲ Green / ▼ Red | Green if +, Red if — |
| **Bias** | PCR heuristic + support OI check | **Base:** Strong Bull (≥1.4), Bull (≥1.15), Neutral (0.85–1.15), Bear (0.65–0.85), Strong Bear (<0.65). **Nudge:** If spot < 75 pts from support & support Under Pressure, downgrade one level (e.g., Bull → Neutral) | — | Color badge: 🟢 Strong Bull, 🔵 Bull, 🟡 Neutral, 🔴 Bear, 🔴 Strong Bear |

### API Fallback Strategy

**PCR fallback chain:**
1. Call `/v2/market/pcr?instrument_key=NSE_INDEX|Nifty 50&expiry=YYYY-MM-DD&date=today&bucket_interval=5`
2. Try `response.data.insights[-1].pcr` (latest 5-min bucket)
3. If missing, fall back to `response.data.pcr` (overall day PCR)
4. If API fails/timeout, compute locally: `sum(PE OI across 13 subscribed strikes) / sum(CE OI)` 
5. Log ℹ️ if local fallback used, ⚠️ if API error

**Max Pain fallback chain:**
1. Call `/v2/market/max-pain?instrument_key=NSE_INDEX|Nifty 50&expiry=YYYY-MM-DD&date=today&bucket_interval=5`
2. Try `response.data.insights[-1].max_pain` (latest 5-min bucket)
3. If missing, fall back to `response.data.max_pain` (overall day Max Pain)
4. If API fails/timeout, brute-force calculate: test each subscribed strike as candidate, for each candidate sum `abs(candidate - strike) × oi_strike`, return candidate with minimum pain
5. Log ℹ️ if local fallback used, ⚠️ if API error

### CSV Export
**Filename:** `nifty_tba_YYYY-MM-DD.csv` (date-stamped per IST)

**Columns:** Time | Nifty Spot | PCR | Put ATM OI | Put ATM-1 OI | Call ATM OI | Call ATM+1 OI | IV | VIX | Support/Resistance | Max Pain | Fut OI Chg % | Bias

---

## Footprint Logic

**Method:** Intrabar  
- `price > open` → Buy volume  
- `price < open` → Sell volume  
- `price == open` (doji) → compare with previous close  

**Tick size:** 0.25 (futures), 0.05 (options footprint)  
**Lot size:** Enforced per instrument (NIFTY=**65**, BANKNIFTY=30). Volume rounded down to nearest lot.  
**Options footprint:** Uses raw contract count (no lot-size flooring) — options VTT is already in individual contracts.  
**Volume source:** VTT (Volume Traded Today) delta between ticks

---

## Instrument Manager

- Downloads instrument master from `https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz`
- Cached to `instruments_cache.json`, refreshed every 24 hours
- Provides NIFTY and BANKNIFTY front-3-month futures contracts for the dropdown
- Used to resolve option strike instrument keys for WebSocket subscription

---

## Key Classes

| Class | File | Purpose |
|-------|------|---------|
| `UpstoxAPI` | `footprint_web_app_upstox.py` | Per-user state: token, WebSocket, footprint processor, options cache, OI history, ATM footprint state |
| `FootprintProcessor` | `footprint_web_app_upstox.py` | Classifies volume ticks as buy/sell |
| `DataStorage` | `footprint_web_app_upstox.py` | SQLite read/write, resampling, DB routing |
| `InstrumentManager` | `instrument_manager.py` | Instrument master download/cache/lookup |
| `UpstoxWebSocketV3` | `upstox_websocket_v3.py` | WebSocket client with reconnect |

## ATM Lock — Options Footprint Chart

The following `UpstoxAPI` fields are set **once at login** (first call to `subscribe_options_strikes`) and never changed again during the session:

| Field | Description |
|-------|-------------|
| `atm_fp_strike` | Locked ATM strike value (e.g. `24500`) |
| `atm_fp_ce_key` | Instrument key for the locked ATM CE contract |
| `atm_fp_pe_key` | Instrument key for the locked ATM PE contract |
| `atm_fp_expiry` | Expiry date string for display (e.g. `05 Jun 2026`) |

When the ATM monitor re-subscribes options after a spot move, these fields are unchanged — the options footprint chart continues recording ticks for the original ATM CE/PE contracts.

All other features (`options_chain`, `straddle`, `oi_tracker`, `volatility_skew`, `option_chain_full`, `roc`, `tba_snapshot`) derive ATM dynamically from `round(nifty_spot_ltp / 50) * 50` on every API call and are unaffected by the lock.

### Additional UpstoxAPI State Variables

| Variable | Description |
|----------|-------------|
| `vix_ltp` | Live India VIX — updated from `NSE_INDEX\|India VIX` WebSocket subscription (ltpc mode). Used by `/api/tba-snapshot`. |

### Socket.IO Events

| Event | Direction | Description |
|-------|-----------|-------------|
| `ohlc_data` | Server → Client | Futures candle + footprint tick (existing) |
| `options_fp_data` | Server → Client | ATM CE/PE option candle + footprint tick. Includes `opt_type: 'CE'|'PE'` field to route to the correct chart half |

---

## Common Tasks & Troubleshooting

### Add a new tab/feature
1. Add JavaScript function in `chart.html` (e.g., `loadNewTab()`)
2. Add Flask route in `footprint_web_app_upstox.py` (e.g., `/api/new-endpoint`)
3. Add tab button to the sidebar: `<button class="tab-btn" id="tab-new" onclick="switchTab('new')">🔲</button>`
4. Update `switchTab()` function to handle the new tab visibility/hiding
5. Test locally, commit, push, redeploy

### Update Upstox API calls
- PCR: `/v2/market/pcr` with params `instrument_key`, `expiry`, `date`, `bucket_interval=5`
- Max Pain: `/v2/market/max-pain` with same params
- Both use `ANALYTICS_TOKEN` for authorization
- Fallback to local calculation if API fails or times out

### Debug WebSocket issues
```bash
# Monitor live ticks on the server
journalctl -u finalfootprint -f | grep -E "(WebSocket|subscribe|process)"

# Check if instrument keys are correct
grep "instrument_key" /opt/finalfootprint/footprint_web_app_upstox.py
```

### Reset database or clear old data
```bash
# Manual cleanup
rm /opt/finalfootprint/footprint_data_*.db

# Cleanup runs automatically on app restart (180-day retention)
systemctl restart finalfootprint
```

### Update NIFTY lot size globally
- Search for `NIFTY_LOT_SIZE = 65` in `footprint_web_app_upstox.py`
- Also check BANKNIFTY: `BANKNIFTY_LOT_SIZE = 30`
- Redeploy after changes

### Export historical data
- TBA snapshots: Use 📊 tab "⬇ CSV" button to export current session
- Futures candles: Query SQLite directly: `sqlite3 footprint_data_NIFTY.db "SELECT * FROM candles LIMIT 100;"`

---

## Known Limitations & Workarounds

### Limitations
- **Eventlet worker deprecated:** Gunicorn 25+ removed eventlet. Upgrade to gevent before Gunicorn v26.
- **Single worker only:** Multiple Gunicorn workers would break Socket.IO state sharing (session not sync'd).
- **Options data 13 strikes only:** PCR/Max Pain from full Upstox API, but IV/SR calculated from 13 near-ATM subscribed strikes only.
- **OI change % shows — for first N minutes:** Until `oi_history` accumulates 3+ ticks for each interval.
- **Browser cache:** Clear cache if seeing stale chart after deployment (`Cmd+Shift+R` on Mac).

### Workarounds & Fixes
- **WebSocket reconnection slow:** Increase `wait_for_connection()` timeout in `/opt/finalfootprint/upstox_websocket_v3.py` if needed.
- **ATM options footprint locked forever:** By design — restart app to unlock and recalculate ATM.
- **API timeout (PCR/Max Pain):** Catch exception in `/api/tba-snapshot`, uses local fallback automatically (check logs for ℹ️ entry).
- **IV calculation returns None:** Check if option LTP < intrinsic value (algorithm rejects such inputs).
- **Chart x-axis shows UTC instead of IST:** Ensure client browser timezone is set correctly; server sends IST offset (+19800s).

### Common Error Messages
| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Session expired or invalid token | Logout & re-login, check token expiry date |
| `WebSocket timeout` | Network lag or Upstox API slow | Restart WebSocket, check firewall |
| `Database locked` | Multiple processes accessing DB | Stop app, remove `.db-journal`, restart |
| `EventEmitter memory leak warning` | Too many listeners on WebSocket close/end | Normal in eventlet mode, no action needed |

---

## Backup & Recovery

**Restore from backup files (if a change breaks the app):**
```bash
cp /opt/finalfootprint/footprint_web_app_upstox.py.backup_20260321_110147 /opt/finalfootprint/footprint_web_app_upstox.py
cp /opt/finalfootprint/templates/login_upstox.html.backup_20260321_110147 /opt/finalfootprint/templates/login_upstox.html
systemctl restart finalfootprint
```

**Restore from git:**
```bash
cd /opt/finalfootprint
git checkout feature/options-chain-websocket-stability -- footprint_web_app_upstox.py
systemctl restart finalfootprint
```

---

## Dependencies (requirements_upstox.txt)

```
requests>=2.25.1
flask>=2.0.0
flask-socketio>=5.0.0
simple-websocket>=0.9.0
gunicorn>=20.1.0
eventlet>=0.33.3
websocket-client>=1.6.0
protobuf>=4.21.0
```

---

---

## Session History & Changes

| Session | Date | Key Changes |
|---------|------|-------------|
| Session 1 | 21 Mar 2026 | Initial app launch — analytics token login, auto session cron, chart reordering |
| Session 2 | 10 Apr 2026 | Options chain triggers (T1/T2/T3), all-triggers log, volatility skew, full option chain |
| Session 3 | 3 May 2026 | Rate of Change tab, footprint alert bell, OI spike highlighting |
| Session 4 | 5 June 2026 | NIFTY Option Chain Time-Based Analysis tab, India VIX subscription, PCR/Max Pain via Upstox APIs, capture schedule 09:18+ every 5 min, Options Footprint chart with ATM lock, top 3 OI gradient highlighting |
| Session 5 | 8 June 2026 | Documentation review & update, all features verified working |
| Session 6 | 17 June 2026 | Trace filter default updated to 10000, TBA auto-capture on login, Options Footprint multi-strike real-time updates with dropdown selection, comprehensive fixes for chart display and offset filtering |

---

### Session 6 Updates (17 June 2026) — Major Options Footprint Enhancements

**Overview:**
Fixed critical issues with Options Footprint chart real-time updates and multi-strike selection. The chart now displays live data for all 7 strike offsets (ATM ±300, ±200, ±100, ATM) with smooth dropdown switching and real-time WebSocket updates.

**Changes Made:**

#### 1. Trace Filter Default Value Updated
- **File:** `templates/chart.html` (line 305)
- **Change:** Default trace value changed from `100000` to `10000`
- **Reason:** Lower sensitivity for detecting lower-volume trades in main futures footprint chart
- **Scope:** Affects NIFTY/BANKNIFTY futures footprint chart only (Chart tab)

#### 2. TBA Auto-Capture on Login
- **File:** `templates/chart.html` (line 953)
- **Change:** Added `tbaInitPanel()` call to socket connect event handler
- **Behavior:** 
  - Upon successful login, the TBA capture scheduler activates automatically
  - First snapshot triggers at 09:18 IST (or next `:X3/:X8` boundary after market open)
  - Subsequent snapshots every 5 minutes (09:23, 09:28, 09:33, etc.)
  - Users no longer need to manually click "📸 Capture Now" to begin data collection
- **Data Collection:** Happens transparently in the background; TBA panel not required to be open
- **Manual Option:** Users can still click "📸 Capture Now" at any time to force an immediate snapshot

#### 3. Options Footprint Real-Time Updates - Critical Fixes ✅

**Issue 1: Missing Offset Field in Socket Events**
- **File:** `footprint_web_app_upstox.py` (line 844)
- **Fix:** Added `'offset': 0` to base_update in `_process_atm_option_footprint()`
- **Impact:** Frontend can now filter Socket.IO events by offset correctly

**Issue 2: ATM Footprint Processing Never Called**
- **File:** `footprint_web_app_upstox.py` (lines 1052-1063)
- **Fix:** Added checks for ATM CE/PE instrument keys in `process_websocket_data()`
- **Impact:** Real-time Socket.IO events now emitted for locked ATM CE/PE contracts

**Issue 3: Non-ATM Offsets (±100, ±200, ±300) Not Emitted in Real-Time**
- **File:** `footprint_web_app_upstox.py` (lines 952-964)
- **Fix:** Added `socketio.emit()` calls to `_process_all_strike_footprints()`
- **Impact:** All 14 strike combinations (7 offsets × 2 types) now emit real-time events for chart updates

**Issue 4: Dropdown Value Always Reset to ATM**
- **File:** `templates/chart.html` (lines 2484, 2793-2797)
- **Fix:** Added `ofpDropdownInitialized` flag to prevent `populateStrikeDropdown()` from being called multiple times
- **Root Cause:** Function was called every time `loadOfpHistory()` ran, resetting dropdown to '0'
- **Impact:** Dropdown selection now persists when user switches between offsets

**Issue 5: Charts Not Displaying Data After Offset Switch**
- **File:** `templates/chart.html` (lines 2808-2835)
- **Fix:** 
  - Added enhanced console logging for debugging
  - Added `fitContent()` call to auto-fit chart after data load
  - Improved data validation and error messages
- **Impact:** Charts now display correctly with proper data for each offset

#### 4. Options Footprint Chart Features Now Working

**Multi-Strike Selection:**
- ✅ Dropdown shows actual strike prices (e.g., 24200, 24300, 24400 instead of "ATM±100")
- ✅ User can select any of 7 strike offsets (ATM ±300, ±200, ±100, ATM)
- ✅ Selection persists and doesn't reset to ATM
- ✅ Charts display correct data immediately upon selection

**Real-Time Updates:**
- ✅ All 14 strike combinations receive real-time WebSocket ticks
- ✅ Charts update instantly as new ticks arrive
- ✅ Footprint boxes (buy/sell volume) drawn correctly
- ✅ Both CE and PE series update simultaneously

**Data Persistence:**
- ✅ All 14 strike combinations stored in database (`NIFTY_CE_-300` to `NIFTY_CE_300`, same for PE)
- ✅ Current day data loaded from DB when offset selected
- ✅ Historical candles available for all offsets

**Verified via Console Logs:**
```
✅ Setting CE chart data with 13 candles
  First candle: {time: 1781790180, open: 132.05, high: 132.05, low: 132, close: 132.05, …}
  Last candle: {time: 1781791560, open: 120.7, high: 120.95, low: 120.5, close: 120.5, …}
✅ Setting PE chart data with 13 candles
  First candle: {time: 1781790180, open: 106.4, high: 106.55, low: 106.4, close: 106.4, …}
  Last candle: {time: 1781791560, open: 115.8, high: 116.4, low: 115.5, close: 116.15, …}
```

#### 5. Documentation Created

| File | Purpose |
|------|---------|
| `OPTIONS_FP_REALTIME_FIX_DETAILED.md` | Comprehensive analysis of ATM emission fix |
| `DROPDOWN_OFFSET_FIX.md` | Multi-strike offset real-time emission fix |
| `DROPDOWN_VALUE_RESET_FIX.md` | Dropdown persistence fix documentation |
| `OPTIONS_FP_COMPLETE_FIX_SUMMARY.md` | Complete fix summary and verification |
| `VERIFICATION_REPORT.md` | 100pt vs 50pt rounding verification |

---

*Last updated: 17 June 2026 (session 6)*
