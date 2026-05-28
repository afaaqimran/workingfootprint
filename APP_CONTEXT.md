# Afaaqs Foot Print Server — Application Context Document

This document provides a complete reference for any AI system or developer working on this application.

---

## Overview

**Application Name:** Afaaqs Foot Print Server  
**Purpose:** Real-time NIFTY/BANKNIFTY futures footprint chart with options chain, straddle premium tracking, OI tracker, volatility skew chart, and full option chain — powered by Upstox WebSocket market data.  
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

## Repository

| Item | Detail |
|------|--------|
| Primary repo | `https://github.com/afaaqimran/finalfootprint.git` |
| Backup repo | `https://github.com/afaaqimran/Footprintandoptiontrigger.git` |
| Active branch | `feature/options-chain-websocket-stability` |
| GitHub PAT | Stored in git remote URL (use `git remote -v` to check) |
| Clone command | `git clone https://<PAT>@github.com/afaaqimran/finalfootprint.git` |

**To push backup:**
```bash
cd /opt/finalfootprint
git add -A
git commit -m "your message"
git push backup feature/options-chain-websocket-stability
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
├── footprint_data.db               # SQLite DB — default/fallback DB
├── instruments_cache.json          # Cached Upstox instrument master (refreshed every 24h)
├── footprint.service               # Original service file (reference only)
├── templates/
│   ├── chart.html                  # Main chart UI (footprint + options chain + straddle + OI tracker + volatility skew + full option chain tabs)
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
  ├── NSE_INDEX|Nifty 50  → nifty_spot_ltp (for ATM calculation)
  ├── Options keys        → options_cache {ltp, atp, ohlc, volume, oi}
  │                       → oi_history {(timestamp_ms, oi)} rolling 35-min window
  └── Futures token       → OHLC candle + footprint processing
        │
        ├── FootprintProcessor.process_intrabar_footprint()
        │     - Classifies volume as buy/sell (price vs open)
        │     - Rounds to tick size (0.25)
        │     - Enforces lot size rounding
        │
        ├── DataStorage.store_candle() → SQLite (always as 1-min)
        │
        └── socketio.emit('ohlc_data') → browser via Socket.IO
```

---

## WebSocket Subscriptions

On login, the app subscribes to:
1. **Futures instrument** — default NIFTY front-month (e.g. `NSE_FO|37054`), mode `full`
2. **NIFTY 50 spot index** — `NSE_INDEX|Nifty 50`, mode `ltpc`
3. **NIFTY options** — 13 strikes (ATM-300 to ATM+300), both CE and PE, mode `full`

**ATM Monitor thread** — runs every 10 seconds, re-subscribes options if ATM strike shifts by 50 pts (with 15pt hysteresis buffer). Has a 30-second cooldown between re-subscriptions and waits up to 30s for NIFTY spot on startup to prevent rapid-fire re-subscription loops.

---

## Database

| DB file | Contents |
|---------|----------|
| `footprint_data_NIFTY.db` | NIFTY 1-min candles + footprint levels |
| `footprint_data_BANKNIFTY.db` | BANKNIFTY (created on first BANKNIFTY data) |
| `footprint_data.db` | Default fallback |

**Tables:**
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

---

## Frontend UI (chart.html)

Six tabs at the bottom of the screen:

### 📈 Chart Tab
- Lightweight Charts candlestick chart
- Footprint canvas overlay (buy/sell volume at each price level)
- Timeframe selector (1/3/5/15 min)
- Symbol selector (NIFTY/BANKNIFTY futures)
- Draw lines tool
- Historical data loaded on login via `/api/stored-data`
- Live updates via Socket.IO `ohlc_data` event
- X-axis shows date + time in IST (`dd Mon, HH:MM`)
- Chart height: `calc(100vh - 36px)` to avoid tab bar overlap

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

## Footprint Logic

**Method:** Intrabar  
- `price > open` → Buy volume  
- `price < open` → Sell volume  
- `price == open` (doji) → compare with previous close  

**Tick size:** 0.25  
**Lot size:** Enforced per instrument (NIFTY=75, BANKNIFTY=30). Volume rounded down to nearest lot.  
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
| `UpstoxAPI` | `footprint_web_app_upstox.py` | Per-user state: token, WebSocket, footprint processor, options cache, OI history |
| `FootprintProcessor` | `footprint_web_app_upstox.py` | Classifies volume ticks as buy/sell |
| `DataStorage` | `footprint_web_app_upstox.py` | SQLite read/write, resampling |
| `InstrumentManager` | `instrument_manager.py` | Instrument master download/cache/lookup |
| `UpstoxWebSocketV3` | `upstox_websocket_v3.py` | WebSocket client with reconnect |

---

## Known Issues / Notes

- Gunicorn eventlet worker is deprecated as of Gunicorn 25 (will be removed in v26). Migration to gevent is recommended before upgrading Gunicorn.
- `thread.join()` is incompatible with eventlet — logout uses `stop_event.set()` + `ws.close()` instead of `disconnect()` to avoid crash.
- Only 1 Gunicorn worker — required for Socket.IO state consistency (multiple workers would not share session state).
- Analytics token is hardcoded in source — treat as sensitive credential, do not commit to public repos.
- OI change % columns show `—` during the first N minutes after login (until `oi_history` accumulates enough data for each interval).

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

*Last updated: 14 May 2026 (session 2)*
