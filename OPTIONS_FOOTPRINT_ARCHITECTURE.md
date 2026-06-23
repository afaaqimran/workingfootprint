# Options Footprint Chart — Architecture & Component Diagram

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        UPSTOX WEBSOCKET STREAM                          │
│        Real-time option ticks for all subscribed instruments            │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
          ┌─────────────────┐            ┌─────────────────────┐
          │  NIFTY_CE_24100 │            │  NIFTY_PE_24100     │
          │   (ATM)         │            │   (ATM)             │
          │   LTP, Volume   │            │   LTP, Volume       │
          └────────┬────────┘            └──────────┬──────────┘
                   │                                │
        ┌──────────┴────────────────┬───────────────┴──────────────┐
        │                           │                              │
        ▼                           ▼                              ▼
    ATM Process          ┌──────────────────────────────┐    ATM Process
    _process_atm_        │  All-Strike Processing        │    _process_atm_
    option_footprint     │  _process_all_strike_         │    option_footprint
                         │  footprints()                 │
                         │                               │
                         │  For each offset:             │
                         │  -300, -200, -100,            │
                         │  100, 200, 300               │
                         └───────────┬────────────────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    ▼                ▼                ▼
            ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
            │   CE Build   │  │   PE Build   │  │  All Offsets │
            │   Candle     │  │   Candle     │  │   Build      │
            │   Footprint  │  │   Footprint  │  │   Candles    │
            └──────────────┘  └──────────────┘  └──────────────┘
                    │                ▼                ▼
                    └────────────────┬────────────────┘
                                     │
                    ┌────────────────┴─────────────────┐
                    ▼                                  ▼
            ┌──────────────────┐            ┌──────────────────┐
            │   Store to DB    │            │  Socket.IO Emit  │
            │ (footprint_data_ │            │ 'options_fp_data'│
            │  OPTIONS_ATM.db) │            │  (All 14 offsets)│
            └──────────────────┘            └────────┬─────────┘
                    │                                │
                    │        ┌───────────────────────┘
                    │        │
                    ▼        ▼
            ┌──────────────────────────────┐
            │    DATABASE STORAGE          │
            │  footprint_data_OPTIONS_ATM  │
            │                              │
            │  Symbols stored:             │
            │  - NIFTY_CE_0 (ATM)         │
            │  - NIFTY_CE_-100            │
            │  - NIFTY_CE_100             │
            │  - NIFTY_CE_-200            │
            │  - NIFTY_CE_200             │
            │  - NIFTY_CE_-300            │
            │  - NIFTY_CE_300             │
            │  - NIFTY_PE_0 (ATM)         │
            │  - ... (7 PE offsets)       │
            │                              │
            │  14 TOTAL COMBINATIONS      │
            └──────────────────────────────┘
```

---

## Frontend Components

```
┌─────────────────────────────────────────────────────────────────────────┐
│                   BROWSER TAB: Options Footprint                        │
│                                                                          │
│  ┌────────────────────────────────────────────────────────────────────┐│
│  │                      TOOLBAR (Independent)                         ││
│  │                                                                     ││
│  │  Spot: 24078.35   ATM Lock: 24100   Expiry: 23 Jun 2026          ││
│  │  Strike: [24100 ▼]  TF: [1m][3m][5m][15m]                        ││
│  │  ⚙️ Footprint OFF   Buy≥ 200000   Sell≥ 200000   Trace≥ 100000   ││
│  │                                                                     ││
│  └────────────────────────────────────────────────────────────────────┘│
│                                                                          │
│  ┌────────────────────────┐  ┌────────────────────────────────────────┐│
│  │   CE CHART             │  │   PE CHART                             ││
│  │ (LightweightCharts)    │  │ (LightweightCharts)                   ││
│  │                        │  │                                        ││
│  │ 📈 ATM CALL (CE)       │  │ 📉 ATM PUT (PE)                        ││
│  │ LTP: ₹132.05           │  │ LTP: ₹115.65                          ││
│  │                        │  │                                        ││
│  │  ┌──────────────────┐  │  │  ┌──────────────────────────────────┐ ││
│  │  │ Candlesticks     │  │  │  │ Candlesticks                     │ ││
│  │  │ (OHLC bars)      │  │  │  │ (OHLC bars)                     │ ││
│  │  │                  │  │  │  │                                  │ ││
│  │  │  ▲ 133.5         │  │  │  │  ▲ 117.2                         │ ││
│  │  │  │ 132.1 ║       │  │  │  │  │ 116.0 ║                       │ ││
│  │  │  └─ 131.8 ║      │  │  │  │  └─ 115.3 ║                      │ ││
│  │  │    132.05        │  │  │  │    115.65                        │ ││
│  │  │                  │  │  │  │                                  │ ││
│  │  │  Canvas Overlay  │  │  │  │  Canvas Overlay                  │ ││
│  │  │  (Footprint)     │  │  │  │  (Footprint)                     │ ││
│  │  │                  │  │  │  │                                  │ ││
│  │  │ [300K ║ 250K]    │  │  │  │ [350K ║ 280K]                    │ ││
│  │  │  Buy    Sell     │  │  │  │  Buy    Sell                     │ ││
│  │  │                  │  │  │  │                                  │ ││
│  │  └──────────────────┘  │  │  └──────────────────────────────────┘ ││
│  └────────────────────────┘  └────────────────────────────────────────┘│
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Processing Pipeline

### Real-Time Tick Processing (Per Tick)

```
1 WebSocket Tick
    ↓
process_websocket_data()
    ├─ Check: instrument_key == atm_fp_ce_key?
    │   ├─ YES → _process_atm_option_footprint('CE')
    │   │         └─ Emit: 'options_fp_data' {opt_type: 'CE', offset: 0}
    │   └─ NO
    │
    ├─ Check: instrument_key == atm_fp_pe_key?
    │   ├─ YES → _process_atm_option_footprint('PE')
    │   │         └─ Emit: 'options_fp_data' {opt_type: 'PE', offset: 0}
    │   └─ NO
    │
    └─ For each non-ATM offset in options_meta:
        ├─ Check: instrument_key match?
        │   ├─ YES → _process_all_strike_footprints(offset)
        │   │         └─ Emit: 'options_fp_data' {opt_type, offset}
        │   └─ NO
```

### Candle Building

```
Current Tick:  LTP=132.05, Volume=8954321

Compare with Previous:
  prev_ltp=132.03, prev_volume=8941821
  
Volume Diff: 8954321 - 8941821 = 12500 contracts

Determine Buy/Sell:
  if (LTP > previous_close): BUY
  if (LTP < previous_close): SELL
  if (LTP = previous_close): HOLD (use previous category)

Footprint Processing:
  price_level=132.05
  buy_qty=12500, sell_qty=0  (or split by bid/ask)
  
Update Candle:
  time_bucket = 1781791560000 (1-min floor)
  
  if (candle exists for bucket):
    high = max(high, 132.05)
    low = min(low, 132.05)
    close = 132.05
    footprint_levels[132.05] += {buy: 12500, sell: 0}
  else:
    new candle: {
      timestamp: 1781791560000,
      open: 132.05,
      high: 132.05,
      low: 132.05,
      close: 132.05,
      footprint_levels: {132.05: {buy: 12500, sell: 0}}
    }

Emit Event:
  socketio.emit('options_fp_data', {
    symbol: 'NIFTY_CE_0',
    opt_type: 'CE',
    offset: 0,
    timestamp: 1781791560000,
    open: 132.05, high: 132.05, low: 132.05, close: 132.05,
    ltp: 132.05,
    volume: 8954321,
    volume_diff: 12500,
    footprint_level: {price: 132.05, buy_qty: 12500, sell_qty: 0},
    historical: false
  })

Store to DB:
  INSERT INTO candles (symbol, offset, ...) VALUES (...)
```

---

## Frontend Update Flow

### 1. WebSocket Connection Established

```javascript
socket.on('options_fp_data', (data) => {
    ofpHandleLiveTick(data);
});
```

### 2. Real-Time Tick Received

```
Tick: {opt_type: 'CE', offset: 0, timestamp: 1781791560000, ltp: 132.05, ...}
    ↓
ofpHandleLiveTick(data)
    ├─ Extract offset: dataOffset = 0
    ├─ Check: dataOffset === ofpCurrentOffset? (0 === 0? YES)
    │   ├─ YES: Process
    │   └─ NO: Skip (return early)
    │
    ├─ Update header LTP: ofpCeLtp.textContent = '₹132.05'
    │
    ├─ Find candle in ofpCeData array by timestamp
    │   ├─ Found: Update existing
    │   │   ├─ high = max(high, ltp)
    │   │   ├─ low = min(low, ltp)
    │   │   ├─ close = ltp
    │   │   └─ footprint_levels[132.05].buy_qty += 12500
    │   │
    │   └─ Not found: Create new
    │       └─ Push new candle to array
    │
    ├─ Update candlestick: series.update({...})
    │
    └─ If ofpFpEnabled: drawOfpFootprint('CE')
        └─ Redraw canvas overlay
```

### 3. User Switches Strike

```
User selects "24300" (ATM+200) from dropdown
    ↓
switchOfpStrike()
    ├─ newOffset = '200'
    ├─ ofpCurrentOffset = '200'
    │
    ├─ loadOfpHistory('CE')
    │   ├─ Fetch: /api/options-footprint-data?type=CE&offset=200&days=1
    │   │
    │   ├─ API Response: {data: [...715 candles...], offset: '200'}
    │   │
    │   ├─ Resample to ofpTimeframe (if > 1-min)
    │   ├─ Build live array
    │   ├─ Update ofpCeData = liveArr
    │   ├─ Update candlestick: series.setData(liveArr)
    │   ├─ Fit content: chart.timeScale().fitContent()
    │   └─ drawOfpFootprint('CE')
    │
    ├─ loadOfpHistory('PE')
    │   └─ Same as CE but for PE
    │
    └─ Real-time updates now filter for offset='200' only
```

### 4. Footprint Rendering

```
drawOfpFootprint('CE')
    ├─ Get visible candles from chart
    │
    ├─ For each visible candle:
    │   ├─ Get footprint_levels object
    │   │
    │   └─ For each price level:
    │       ├─ Calculate pixel position (x, y)
    │       │
    │       ├─ Check filters:
    │       │   ├─ buy_qty >= ofpBuyFilter?
    │       │   └─ sell_qty >= ofpSellFilter?
    │       │
    │       ├─ Draw BUY box (right side):
    │       │   ├─ Width ∝ buy_qty
    │       │   ├─ Color: Green (#26a69a)
    │       │   └─ Position: x + 14 (right of candle center)
    │       │
    │       └─ Draw SELL box (left side):
    │           ├─ Width ∝ sell_qty
    │           ├─ Color: Red (#ef5350)
    │           └─ Position: x - 14 (left of candle center)
```

---

## State Management

### Backend State Per Combination

```python
# For each of 14 strike/type combinations

ofp_strike_candles[symbol]      # Current candle being built
ofp_strike_volumes[symbol]      # Previous VTT (volume traded today)
ofp_strike_close[symbol]        # Previous close price
ofp_strike_category[symbol]     # 'buy' or 'sell' for next category
ofp_strike_fp_proc[symbol]      # FootprintProcessor instance

# Example: NIFTY_CE_0 (ATM CE)
ofp_strike_candles['NIFTY_CE_0'] = {
    'ts': 1781791560000,
    'open': 132.05,
    'high': 132.05,
    'low': 132.00,
    'close': 132.05
}
```

### Frontend State

```javascript
// Global variables
let ofpCeData = [];           // Array of candles for CE
let ofpPeData = [];           // Array of candles for PE
let ofpCurrentOffset = '0';   // Selected offset
let ofpAtmStrike = 24100;     // Locked ATM value
let ofpFpEnabled = false;     // Footprint display on/off
let ofpTimeframe = '1';       // Chart timeframe (1/3/5/15)

// Example: CE data for offset 0
ofpCeData = [
    {
        time: 1781790180 + 19800,  // IST seconds
        open: 132.05,
        high: 132.05,
        low: 132.00,
        close: 132.05,
        footprint_levels: {
            132.05: {buy_qty: 8000, sell_qty: 4500},
            132.00: {buy_qty: 6500, sell_qty: 7200},
            131.95: {buy_qty: 5200, sell_qty: 3800}
        }
    },
    // ... 12+ more candles per trading session
]
```

---

## Memory & Performance Metrics

### Data Structure Size

| Item | Size | Count | Total |
|------|------|-------|-------|
| 1 Candle | ~500 bytes | 1000 | 500 KB |
| Footprint levels per candle | ~50 bytes × 150 levels | 7500 | 375 KB |
| Per offset/type combination | — | 1 | 875 KB |
| All 14 combinations | — | 14 | 12.25 MB |

### Processing Per Tick

| Task | Time | Frequency |
|------|------|-----------|
| WebSocket parse | 1-2ms | 2-3 ticks/sec |
| ATM footprint processing | 5ms | 2-3 times/sec |
| All-strike processing (×7) | 3-5ms | 2-3 times/sec |
| Database write | 2-3ms | 14 times/sec |
| Socket.IO emit | 1ms | 14 times/sec |

### Browser Rendering

| Task | Time | Trigger |
|------|------|---------|
| Chart update (candlestick) | 5-10ms | Per tick for current offset |
| Footprint redraw | 20-50ms | On visible range change |
| Dropdown repopulate | 5ms | Once per session |

---

## Database Schema

### Table: candles

```
+-------------------+----------+
| Column            | Type     |
+-------------------+----------+
| id                | INTEGER  |
| symbol            | TEXT     | ← NIFTY_CE_0, NIFTY_PE_100, etc.
| opt_type          | TEXT     | ← CE or PE
| offset            | INTEGER  | ← -300 to +300
| timestamp         | INTEGER  | ← unix milliseconds
| open              | REAL     |
| high              | REAL     |
| low               | REAL     |
| close             | REAL     |
| ltp               | REAL     |
| volume            | INTEGER  |
| volume_diff       | INTEGER  |
| footprint_level   | JSON     | ← {price, buy_qty, sell_qty}
| historical        | BOOLEAN  |
+-------------------+----------+
```

### Indexing

```sql
CREATE INDEX idx_symbol_timestamp ON candles(symbol, timestamp);
CREATE INDEX idx_offset ON candles(offset);
```

---

## Error Handling & Recovery

### Missing Data

```
API Request: /api/options-footprint-data?type=CE&offset=200&days=1
    ↓
Response: {success: false, message: "No data for offset"}
    ↓
Frontend:
    ├─ Set status: "Waiting for first tick..."
    ├─ Don't update chart (keep previous data)
    └─ Log: "⚠️ No data for CE, offset=200"
```

### WebSocket Disconnect

```
socket.on('disconnect', () => {
    // Real-time updates stop
    // But historical data still displays
    // Auto-reconnect triggers after 3s
});
```

### Chart Not Initialized

```
if (ofpInitialized === false):
    └─ Wait for 'chart-ready' event
    └─ Then call initOptFPCharts()
```

---

## Summary

**Component**: Options Footprint Chart with multi-strike support

**14 Strike Combinations**: All subscribed, stored, emitted, displayable

**Real-Time**: WebSocket → Process → Emit → Filter → Display

**Data Persistence**: Automatic for all offsets (not just selected)

**UI Independence**: Toolbar separate from main chart controls

**Performance**: 14 emissions per tick, optimized frontend filtering

---

**Last Updated**: June 23, 2026  
**Status**: ✅ Complete Implementation
