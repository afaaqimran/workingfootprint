# Options Footprint Chart — Complete Behavior Analysis

## Overview
The Options Footprint Chart is a real-time analysis tool that displays CE (Call) and PE (Put) option prices with volume footprints. It supports multi-strike monitoring (ATM ± 300 points in 100-point increments) and independent toolbar controls.

---

## Architecture & Data Flow

### 1. Multi-Strike Architecture
- **7 Strike Offsets**: `-300, -200, -100, 0 (ATM), +100, +200, +300`
- **14 Total Combinations**: 7 offsets × 2 types (CE/PE)
- **Symbols**: `NIFTY_CE_0`, `NIFTY_CE_-100`, `NIFTY_PE_100`, etc.
- **Database**: `footprint_data_OPTIONS_ATM.db` stores all 14 combinations automatically
- **UI Selection**: User can switch between any of the 7 strikes via dropdown

### 2. Real-Time Data Flow

```
WebSocket Tick (Upstox)
        ↓
process_websocket_data() [backend]
        ↓
    ├─ Check if ATM CE/PE key
    │   ├─ _process_atm_option_footprint('CE'/'PE')
    │   │   ├─ Build 1-min candle
    │   │   ├─ Calculate footprint (buy/sell volume)
    │   │   ├─ Emit via Socket.IO: 'options_fp_data' (offset=0)
    │   │   └─ Store to DB
    │   └─ END
    │
    └─ Check if Non-ATM offset key (for each meta)
        ├─ _process_all_strike_footprints(offset)
        │   ├─ Build 1-min candle for this offset
        │   ├─ Calculate footprint (buy/sell volume)
        │   ├─ Emit via Socket.IO: 'options_fp_data' (offset=specified)
        │   └─ Store to DB
        └─ END

                ↓
        Socket.IO Event
                ↓
Frontend (chart.html)
        ├─ socket.on('options_fp_data', data)
        │   ├─ Filter: if data.offset !== ofpCurrentOffset, skip
        │   ├─ Update header LTP
        │   ├─ ofpHandleLiveTick(data)
        │   │   ├─ Update/create candle in ofpCeData or ofpPeData
        │   │   ├─ Merge footprint levels (buy_qty, sell_qty)
        │   │   ├─ Update candlestick series
        │   │   └─ Redraw footprint overlay if enabled
        │   └─ END
        └─ END
```

---

## Backend Implementation

### Initialization (Login)

**Location**: `subscribe_options_strikes()` in `footprint_web_app_upstox.py` (lines 214-217)

```python
# Subscribe to all 14 strike combinations
for offset in [-300, -200, -100, 0, 100, 200, 300]:
    for opt_type in ['CE', 'PE']:
        strike = atm_strike + offset
        subscribe(instrument_key)  # Both ATM and non-ATM
```

- **ATM Strike**: Locked at login, calculated as `round(nifty_spot / 100) * 100`
- **Subscription**: All 14 instruments subscribe to WebSocket simultaneously
- **State**: Backend maintains separate state for each combination

### Real-Time Processing

#### 1. ATM Processing: `_process_atm_option_footprint()` (Line 786)

**Triggered when**:
```python
if instrument_key == self.atm_fp_ce_key and ltp_val > 0:
    _process_atm_option_footprint(opt_type='CE', ...)
elif instrument_key == self.atm_fp_pe_key and ltp_val > 0:
    _process_atm_option_footprint(opt_type='PE', ...)
```

**Processing**:
1. Receive LTP and volume from WebSocket tick
2. Build 1-minute candle (OHLC)
3. Calculate volume difference from previous tick
4. Process volume through footprint processor (categorizes as buy/sell)
5. Emit Socket.IO event with `offset=0`
6. Store to database

**State Maintained Per Type**:
- `atm_ce_candle`, `atm_ce_prev_volume`, `atm_ce_prev_close`, `atm_ce_prev_category`
- `atm_pe_candle`, `atm_pe_prev_volume`, `atm_pe_prev_close`, `atm_pe_prev_category`

#### 2. All-Strike Processing: `_process_all_strike_footprints()` (Line 882)

**Triggered for each offset**:
```python
for meta in self.options_meta:
    if meta.get('instrument_key') == instrument_key and ltp_val > 0:
        offset = meta.get('offset', 0)
        _process_all_strike_footprints(
            instrument_key=instrument_key,
            opt_type=meta['type'],
            offset=offset,
            ltp=ltp_val,
            vtt=int(full.get('vtt', 0)),
            current_ts=current_ts
        )
```

**Processing**:
1. Build symbol: `NIFTY_CE_-300`, `NIFTY_PE_100`, etc.
2. Maintain separate candle state for each strike/type combination
3. Build 1-minute candle (OHLC)
4. Calculate volume difference
5. Process through footprint processor
6. Emit Socket.IO event with `offset=specified_value`
7. Store to database

**State Maintained**:
- `ofp_strike_candles[symbol]` — current candle
- `ofp_strike_volumes[symbol]` — previous volume
- `ofp_strike_close[symbol]` — previous close price
- `ofp_strike_category[symbol]` — buy/sell category
- `ofp_strike_fp_proc[symbol]` — footprint processor instance

### Data Storage

**Location**: `footprint_data_OPTIONS_ATM.db`

**Schema**:
```
symbol: 'NIFTY_CE_0', 'NIFTY_CE_-100', 'NIFTY_PE_100', etc.
opt_type: 'CE' or 'PE'
offset: -300, -200, -100, 0, 100, 200, 300
timestamp: Unix milliseconds
open, high, low, close: Price levels
ltp: Last traded price
volume: Total volume traded
volume_diff: Volume in this candle
footprint_level: { price, buy_qty, sell_qty }
```

All 14 combinations store independently with automatic bucketing.

### API Endpoint

**Location**: `/api/options-footprint-data` (Line 1765)

**Parameters**:
```
type: 'CE' or 'PE'
offset: '0', '-100', '100', '-200', '+200', '-300', '+300'
days: 1 (default) — only current day
```

**Response**:
```json
{
  "success": true,
  "data": [...candles...],
  "count": 857,
  "opt_type": "CE",
  "offset": "0",
  "locked_strike": 24100,
  "locked_expiry": "23 Jun 2026"
}
```

---

## Frontend Implementation

### Initialization: `initOptFPCharts()` (Line 2705)

**Triggers on tab switch** when user clicks "🕯 Options Footprint" tab

```javascript
1. Create two LightweightCharts (CE and PE)
2. Setup candlestick series for each
3. Create canvas overlays for footprint visualization
4. Load historical data for current offset
5. Setup timeframe buttons (1m, 3m, 5m, 15m)
6. Subscribe to Socket.IO 'options_fp_data' event
```

### State Variables

```javascript
let ofpCeChart, ofpPeChart;           // LightweightCharts instances
let ofpCeSeries, ofpPeSeries;         // Candlestick series
let ofpCeData, ofpPeData;             // Array of candle objects
let ofpFpEnabled = false;             // Footprint visualization on/off
let ofpTimeframe = '1';               // Resample interval (1, 3, 5, 15 min)
let ofpInitialized = false;           // Chart setup complete
let ofpDropdownInitialized = false;   // Dropdown populated (once only)
let ofpCurrentOffset = '0';           // Selected strike offset
let ofpAtmStrike = null;              // Locked ATM strike value
```

### Key Functions

#### 1. `loadOfpHistory(side)` (Line 2770)

**Triggers**:
- Initial chart load
- Timeframe change
- Strike offset change

**Process**:
```javascript
1. Call API: /api/options-footprint-data?type=CE&offset=ofpCurrentOffset&days=1
2. Get array of candle objects with footprint levels
3. Resample to selected timeframe (1/3/5/15 minutes)
4. Build live data array (convert to LightweightCharts format)
5. Update candlestick series: ofpCeSeries.setData(liveArr)
6. Auto-fit chart: ofpCeChart.timeScale().fitContent()
7. Redraw footprint overlay
8. Update status: "857 candles loaded"
```

**Output**:
- `ofpCeData` / `ofpPeData` — array of candles with OHLC + footprint_levels
- Charts display the loaded candles

#### 2. `switchOfpStrike()` (Line 2850)

**Triggers**: User selects different strike from dropdown

```javascript
1. Read new offset from dropdown: selectEl.value
2. Compare with current: if same, return early
3. Update: ofpCurrentOffset = newOffset
4. Reload both CE and PE: loadOfpHistory('CE'); loadOfpHistory('PE');
```

**Dropdown Persistence Fix** (lines 2793-2797):
```javascript
// Only populate dropdown once, ever (uses ofpDropdownInitialized flag)
if (!ofpDropdownInitialized) {
    ofpDropdownInitialized = true;
    populateStrikeDropdown();
}
```

#### 3. `populateStrikeDropdown()` (Line 2875)

**Creates dropdown options**:
```javascript
offsets = [
  { offset: '-300', label: ATM - 300 },
  { offset: '-200', label: ATM - 200 },
  { offset: '-100', label: ATM - 100 },
  { offset: '0',    label: ATM },
  { offset: '100',  label: ATM + 100 },
  { offset: '200',  label: ATM + 200 },
  { offset: '300',  label: ATM + 300 }
]
```

Shows **actual strike prices**, not labels like "ATM+100"

#### 4. `ofpHandleLiveTick(data)` (Line 2910)

**Triggers**: Socket.IO event `socket.on('options_fp_data', data)`

```javascript
1. Extract offset from data: dataOffset = data.offset
2. Filter: if dataOffset !== ofpCurrentOffset, skip (don't update charts)
3. Update LTP header: ofpCeLtp.textContent = '₹' + data.ltp
4. Find candle by timestamp in ofpCeData array
5. If candle exists:
   - Update high/low/close
   - Merge footprint level (buy_qty, sell_qty)
6. If candle doesn't exist:
   - Create new candle with timestamp
   - Add to array (sorted by time)
7. Update candlestick: series.update({...})
8. Redraw footprint overlay if enabled
```

**Filtering**: Only processes ticks for the currently selected offset

#### 5. `drawOfpFootprint(side)` (Line 2595)

**Draws buy/sell volume boxes on chart**:

```javascript
1. Get visible candles from chart.timeScale().getVisibleLogicalRange()
2. For each visible candle:
   - Get footprint_levels object
   3. For each price level:
      - Calculate position on chart (pixel coordinates)
      - Draw buy box (right): width ∝ buy_qty (green if highlighted)
      - Draw sell box (left): width ∝ sell_qty (red if highlighted)
      - Apply filters: only show if buy_qty >= ofpBuyFilter && sell_qty >= ofpSellFilter
4. Render on canvas overlay
```

**Filters**:
- `ofp-buy-filter` (default 200000): Hide levels with buy_qty < threshold
- `ofp-sell-filter` (default 200000): Hide levels with sell_qty < threshold
- `ofp-trace` (default 100000): Hide individual trades < threshold

#### 6. `ofpResample(data, tfMin)` (Line 2515)

**Converts 1-min candles to higher timeframes**:

```javascript
if tfMin == 3:
  Bucket candles into 3-minute periods
  Merge OHLC: Open=first.open, High=max, Low=min, Close=last.close
  Merge footprint_levels: Sum buy_qty and sell_qty per price level
```

Output: Array of candles grouped by target timeframe

#### 7. `ofpBuildLive(flatData)` (Line 2541)

**Converts database response to LightweightCharts format**:

```javascript
1. Convert epoch-ms timestamps to IST (seconds + 19800)
2. Group by timestamp (deduplicate)
3. Build candle objects: { time, open, high, low, close, footprint_levels }
4. Return sorted array by time
```

---

## Toolbar Controls

### Independent from Main Chart Controls

The Options Footprint toolbar has its own separate controls:

| Control | Purpose | Values | Default |
|---------|---------|--------|---------|
| **Strike** | Select which offset to view | -300, -200, -100, 0, 100, 200, 300 | 0 (ATM) |
| **TF** | Resample timeframe | 1m, 3m, 5m, 15m | 1m |
| **⚙️ Footprint** | Toggle footprint visualization | ON/OFF | OFF |
| **Buy≥** | Min buy volume to display | 200000 | 200000 |
| **Sell≥** | Min sell volume to display | 200000 | 200000 |
| **Trace≥** | Min volume per trade | 100000 | 100000 |

### Header Display

```
🕯 Options Footprint
Spot: 24078.35 (live update every 5s)
ATM Lock: 24100 (locked at login, frozen)
Expiry: 23 Jun 2026 (locked at login)
```

### Strike Labels

```
Left side (CE):   📈 ATM CALL (CE)    Strike: 24100
Right side (PE):  📉 ATM PUT (PE)     Strike: 24100
```

Labels update when user switches strikes.

---

## Real-Time Updates

### WebSocket Event Flow

```
Backend emits: socketio.emit('options_fp_data', {
    'symbol': 'NIFTY_CE_0',
    'opt_type': 'CE',
    'offset': 0,
    'timestamp': 1781791560000,
    'open': 132.05,
    'high': 132.05,
    'low': 132.00,
    'close': 132.05,
    'ltp': 132.05,
    'volume': 8954321,
    'volume_diff': 12500,
    'footprint_level': {
        'price': 132.00,
        'buy_qty': 8000,
        'sell_qty': 4500
    },
    'historical': False
})

Frontend receives: ofpHandleLiveTick(data)
  ├─ Filter by offset (skip if not current)
  ├─ Update header LTP
  ├─ Update/create candle in data array
  ├─ Update candlestick series
  └─ Redraw footprint overlay
```

### Update Frequency

- **ATM (Offset 0)**: Emitted on every WebSocket tick
- **Non-ATM Offsets**: Emitted on every WebSocket tick (all 14 combinations process in parallel)
- **Frontend Filter**: Only processes ticks for currently selected offset
- **Chart Refresh**: Footprint redraw triggers on visible range change

---

## Data Persistence

### Storage Strategy

All 14 strike combinations stored **immediately** (not just when selected):

```python
# For each WebSocket tick
for meta in self.options_meta:  # 14 items
    _process_all_strike_footprints(...)  # Process each
    socketio.emit('options_fp_data', ...)  # Emit each
    data_storage.store_candle(...)  # Store each
```

### Loading Strategy

**Current Day Only** (✅ Fixed):
- API defaults to `days=1` (only today's data)
- `get_stored_data()` filters by **trading timestamp** (not record creation time)
- `clear_old_session_data()` removes previous day's candles when `days=1`
- Resets daily at market open
- No historical range selection

**API Path**:
```
/api/options-footprint-data?type=CE&offset=0&days=1
```

---

## User Interactions

### 1. Login

```javascript
1. WebSocket connects
2. All 14 strikes subscribe
3. Backend starts emitting 'options_fp_data'
4. Frontend initializes chart if needed
5. Load history for offset 0 (ATM): loadOfpHistory('CE'); loadOfpHistory('PE');
6. Populate dropdown with actual strike prices
7. Display locked ATM strike (24100) and expiry
```

### 2. View Different Strike

```javascript
User selects "24300" from dropdown
  ↓
dropdown onchange event → switchOfpStrike()
  ├─ ofpCurrentOffset = '200'
  ├─ loadOfpHistory('CE')  // Fetch NIFTY_CE_200 data
  ├─ loadOfpHistory('PE')  // Fetch NIFTY_PE_200 data
  ├─ Chart updates with new strike data
  └─ Real-time updates now filter for offset='200' only
```

### 3. Toggle Footprint Display

```javascript
User clicks "⚙️ Footprint OFF"
  ↓
ofpFpEnabled = !ofpFpEnabled
  ├─ Button text changes
  ├─ Button style changes (green if ON)
  ├─ drawOfpFootprint('CE')  // Redraw canvas
  └─ drawOfpFootprint('PE')  // Redraw canvas
```

### 4. Change Timeframe

```javascript
User clicks "3m"
  ↓
ofpTimeframe = '3'
  ├─ loadOfpHistory('CE')  // Resample to 3-min
  └─ loadOfpHistory('PE')  // Resample to 3-min
```

---

## Performance Considerations

### Memory Usage

- **Data Arrays**: ~1000 candles per offset per type (1 day, 1-min)
- **Footprint Levels**: ~100-500 price levels per candle
- **14 Combinations**: Each stores independently, total ~1.4MB for all strikes

### Rendering Performance

- **Canvas Overlay**: Only renders visible candles (60-80 per screen)
- **Chart Updates**: Lightweight (single candlestick update per tick)
- **Footprint Drawing**: Recalculates on visible range change (lazy)

### WebSocket Load

- **14 Emissions Per Tick**: All offsets emit simultaneously
- **Filtering**: Frontend filters to current offset (reduces processing)
- **Database Writes**: 14 writes per tick (1 per combination)

---

## Common Issues & Solutions

| Issue | Cause | Solution |
|-------|-------|----------|
| Dropdown resets to ATM after click | Missing `ofpDropdownInitialized` flag | ✅ Fixed (line 2793) |
| Charts not showing for non-ATM | Real-time emissions only for ATM | ✅ Fixed (emit for all offsets) |
| Strike data not found | Offset symbol not stored to DB | ✅ Fixed (process all 14 strikes) |
| Footprint not updating | WebSocket not connected or filtered | Check console logs |
| LTP header not updating | Header updates separately from chart | Expected (header = real-time, chart = filtered) |

---

## Summary: Complete Flow

### On Market Open (Login)

1. ✅ Backend subscribes to all 14 strikes
2. ✅ Frontend initializes charts
3. ✅ Load ATM data (offset=0)
4. ✅ Populate dropdown (actual strike prices)
5. ✅ Display locked ATM and expiry

### Real-Time Updates

6. ✅ WebSocket ticks arrive
7. ✅ Process all 14 strikes simultaneously
8. ✅ Emit Socket.IO events for each offset
9. ✅ Store to database (all combinations)
10. ✅ Frontend filters by current offset
11. ✅ Update chart candles and footprint

### User Switches Strike

12. ✅ Dropdown triggers `switchOfpStrike()`
13. ✅ Load new offset data from API
14. ✅ Update charts with new strike
15. ✅ Real-time updates now for new offset

### Footprint Display Toggle

16. ✅ Redraw canvas overlay on/off
17. ✅ Apply buy/sell/trace filters
18. ✅ Show volume boxes at each price level

---

**Last Updated**: June 23, 2026  
**Implementation Status**: ✅ Complete with all 5 critical fixes  
**Database**: `footprint_data_OPTIONS_ATM.db` with all 14 combinations
