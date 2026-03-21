# Afaaqs Foot Print Server — Application Context Document

This document provides a complete reference for any AI system or developer working on this application.

---

## Overview

**Application Name:** Afaaqs Foot Print Server  
**Purpose:** Real-time NIFTY/BANKNIFTY futures footprint chart with options chain and straddle premium tracking, powered by Upstox WebSocket market data.  
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
│   ├── chart.html                  # Main chart UI (footprint + options chain + straddle tabs)
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
  ├── Options keys        → options_cache {ltp, atp, ohlc, volume}
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

**ATM Monitor thread** — runs every 10 seconds, re-subscribes options if ATM strike shifts by 50 pts (i.e. spot crosses a strike boundary). Clears stale cache for dropped strikes.

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
| `/api/options-chain` | GET | NIFTY options chain from WebSocket cache |
| `/api/straddle` | GET | Straddle premiums (CE+PE) per strike |

---

## Frontend UI (chart.html)

Three tabs at the bottom of the screen:

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
- Columns: Type, Strike, Label, ATP, LTP, ATP-LTP, Open, High, Low, Volume, T1 trigger
- Auto-refreshes every 2 seconds from WebSocket cache
- T1 trigger: highlights when ITM ATP-LTP < ATM ATP-LTP

### 🎯 Straddle Tab
- Header: NIFTY Spot, ATM strike, Expiry, Lowest straddle, Day Low/High
- Strike table: ±7 strikes around lowest premium, columns: Strike | CE LTP | PE LTP | Straddle
- Lowest premium strike highlighted with 🎯
- Live premium chart (Chart.js line chart) with zoom/pan (scroll wheel, pinch, drag)
- Reset Zoom button
- Premium spike alerts at 50%, 75%, 100% rise from day low
- Auto-refreshes every 2 seconds

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
| `UpstoxAPI` | `footprint_web_app_upstox.py` | Per-user state: token, WebSocket, footprint processor, options cache |
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

*Last updated: 21 March 2026*
