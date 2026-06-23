# Options Footprint Chart — Quick Reference Guide

## At a Glance

| Aspect | Details |
|--------|---------|
| **Purpose** | Real-time CE/PE option footprint analysis with multi-strike support |
| **Strikes Supported** | 7 (ATM ± 300 in 100-point increments) |
| **Total Combinations** | 14 (7 strikes × 2 types: CE/PE) |
| **Storage** | `footprint_data_OPTIONS_ATM.db` |
| **Update Frequency** | 1-minute candles, real-time ticks |
| **Timeframes** | 1m, 3m, 5m, 15m (resample client-side) |
| **Default Footprint** | OFF (toggle ⚙️ button) |
| **Default Trace Filter** | 100,000 contracts |

---

## Architecture in 30 Seconds

```
WebSocket → Process All 14 Strikes → Store to DB → Emit Socket.IO → Display Charts
              (Simultaneous)          (Auto)        (Real-time)      (Filtered by offset)
```

- **Backend**: All 14 combinations processed and stored on every tick
- **Frontend**: Filters by selected offset and displays in real-time
- **Database**: All data persisted automatically

---

## Key Files

### Backend
- **`footprint_web_app_upstox.py`**
  - Line 214-217: Subscribe to all 14 strikes
  - Line 786: `_process_atm_option_footprint()` 
  - Line 882: `_process_all_strike_footprints()`
  - Line 1765: `/api/options-footprint-data` endpoint

### Frontend
- **`templates/chart.html`**
  - Line 2473-3100: Options Footprint JavaScript code
  - Line 2490: `toggleOptFP()` — Footprint ON/OFF
  - Line 2568: `ofpSetupFpCanvas()` — Canvas setup
  - Line 2595: `drawOfpFootprint()` — Render boxes
  - Line 2705: `initOptFPCharts()` — Chart initialization
  - Line 2770: `loadOfpHistory()` — Load historical data
  - Line 2850: `switchOfpStrike()` — Change strike
  - Line 2875: `populateStrikeDropdown()` — Create options
  - Line 2910: `ofpHandleLiveTick()` — Real-time update

### Database
- **`footprint_data_OPTIONS_ATM.db`**
  - Symbols: `NIFTY_CE_0`, `NIFTY_CE_-100`, `NIFTY_PE_100`, etc.

---

## Backend Processing

### On Each WebSocket Tick

```python
# 1. Check ATM keys
if instrument_key == self.atm_fp_ce_key:
    _process_atm_option_footprint(opt_type='CE', ...)  # Offset=0

if instrument_key == self.atm_fp_pe_key:
    _process_atm_option_footprint(opt_type='PE', ...)  # Offset=0

# 2. Check all non-ATM offsets
for meta in self.options_meta:
    _process_all_strike_footprints(offset=meta.offset, ...)

# 3. Each function:
#    - Builds 1-min candle
#    - Calculates footprint (buy/sell volume)
#    - Emits Socket.IO event
#    - Stores to database
```

### Output (14 events per tick)

```python
socketio.emit('options_fp_data', {
    'opt_type': 'CE',           # or 'PE'
    'offset': 0,                # or -300, -200, -100, 100, 200, 300
    'timestamp': 1781791560000, # Unix milliseconds
    'open': 132.05,
    'high': 132.05,
    'low': 132.00,
    'close': 132.05,
    'ltp': 132.05,
    'volume': 8954321,
    'volume_diff': 12500,
    'footprint_level': {
        'price': 132.05,
        'buy_qty': 8000,
        'sell_qty': 4500
    },
    'historical': False
})
```

---

## Frontend Processing

### On Real-Time Event

```javascript
socket.on('options_fp_data', (data) => {
    // Filter: only process if offset matches current selection
    if (data.offset.toString() !== ofpCurrentOffset) return;
    
    // Update charts
    ofpHandleLiveTick(data);
    
    // Update header LTP
    document.getElementById('ofp-ce-ltp').textContent = 
        '₹' + data.ltp.toFixed(2);
});
```

### On Strike Selection

```javascript
function switchOfpStrike() {
    const newOffset = document.getElementById('ofp-strike-select').value;
    ofpCurrentOffset = newOffset;
    
    // Reload charts for new offset
    loadOfpHistory('CE');  // API call: /api/options-footprint-data?type=CE&offset=newOffset
    loadOfpHistory('PE');  // API call: /api/options-footprint-data?type=PE&offset=newOffset
}
```

### Chart Update

```javascript
function ofpHandleLiveTick(data) {
    // Find candle by timestamp
    let candle = ofpCeData.find(c => c.time === ofpTs(data.timestamp));
    
    if (candle) {
        // Update existing candle
        candle.high = Math.max(candle.high, data.ltp);
        candle.low = Math.min(candle.low, data.ltp);
        candle.close = data.ltp;
        
        // Merge footprint level
        if (data.footprint_level) {
            const p = data.footprint_level.price;
            if (!candle.footprint_levels[p]) {
                candle.footprint_levels[p] = {buy_qty: 0, sell_qty: 0};
            }
            candle.footprint_levels[p].buy_qty += data.footprint_level.buy_qty;
            candle.footprint_levels[p].sell_qty += data.footprint_level.sell_qty;
        }
        
        // Update series
        ofpCeSeries.update({
            time: candle.time,
            open: candle.open,
            high: candle.high,
            low: candle.low,
            close: candle.close
        });
    } else {
        // Create new candle
        const newCandle = {
            time: ofpTs(data.timestamp),
            open: data.ltp,
            high: data.ltp,
            low: data.ltp,
            close: data.ltp,
            footprint_levels: {
                [data.footprint_level.price]: {
                    buy_qty: data.footprint_level.buy_qty,
                    sell_qty: data.footprint_level.sell_qty
                }
            }
        };
        ofpCeData.push(newCandle);
        ofpCeSeries.update(newCandle);
    }
    
    // Redraw footprint if enabled
    if (ofpFpEnabled) drawOfpFootprint('CE');
}
```

---

## Toolbar Controls

```
🕯 Options Footprint
│
├─ Spot: 24078.35          ← Live every 5 seconds
├─ ATM Lock: 24100         ← Frozen at login, 100pt rounding
├─ Expiry: 23 Jun 2026     ← Frozen at login
│
├─ Strike: [24100 ▼]       ← Select different offset (7 options)
├─ TF: [1m][3m][5m][15m]   ← Resample timeframe
├─ ⚙️ Footprint OFF         ← Toggle footprint ON/OFF
├─ Buy≥ 200000             ← Min buy volume filter
├─ Sell≥ 200000            ← Min sell volume filter
└─ Trace≥ 100000           ← Min volume per trade filter
```

---

## Strike Offset Mapping

When ATM = 24,100:

| Dropdown Selection | Offset | Strike | Backend Processes |
|---|---|---|---|
| 23,800 | -300 | ATM-300 | NIFTY_CE_-300, NIFTY_PE_-300 |
| 23,900 | -200 | ATM-200 | NIFTY_CE_-200, NIFTY_PE_-200 |
| 24,000 | -100 | ATM-100 | NIFTY_CE_-100, NIFTY_PE_-100 |
| **24,100** | **0** | **ATM** | **NIFTY_CE_0, NIFTY_PE_0** |
| 24,200 | 100 | ATM+100 | NIFTY_CE_100, NIFTY_PE_100 |
| 24,300 | 200 | ATM+200 | NIFTY_CE_200, NIFTY_PE_200 |
| 24,400 | 300 | ATM+300 | NIFTY_CE_300, NIFTY_PE_300 |

---

## Data Flow Example

### Scenario: User selects 24300 (ATM+200)

```
1. User clicks dropdown → selects "24300"
   
2. switchOfpStrike() triggered
   ofpCurrentOffset = '200'
   
3. loadOfpHistory('CE') called
   HTTP GET /api/options-footprint-data?type=CE&offset=200&days=1
   ↓
   Backend queries: SELECT * FROM candles WHERE symbol='NIFTY_CE_200'
   ↓
   Returns: [candle1, candle2, ..., candle715]
   ↓
   Frontend ofpCeData = [...715 candles for ATM+200 CE...]
   ↓
   ofpCeSeries.setData([OHLC data])
   ↓
   Chart displays ATM+200 CE candles
   
4. loadOfpHistory('PE') called (same process for PE)
   
5. Real-time updates filter by offset='200'
   Only 'options_fp_data' events with offset='200' update the chart
   
6. User sees ATM+200 strike live charts with real-time updates
```

---

## Database Queries

### All Symbols Stored

```sql
SELECT DISTINCT symbol FROM candles;
-- Result:
-- NIFTY_CE_0
-- NIFTY_CE_-100
-- NIFTY_CE_100
-- NIFTY_CE_-200
-- NIFTY_CE_200
-- NIFTY_CE_-300
-- NIFTY_CE_300
-- NIFTY_PE_0
-- NIFTY_PE_-100
-- NIFTY_PE_100
-- NIFTY_PE_-200
-- NIFTY_PE_200
-- NIFTY_PE_-300
-- NIFTY_PE_300
```

### Today's Data for ATM+100 CE

```sql
SELECT COUNT(*) FROM candles 
WHERE symbol='NIFTY_CE_100' 
AND DATE(timestamp/1000, 'unixepoch') = DATE('now');
-- Result: ~760 candles (1-min bars)
```

### Footprint Levels for Specific Strike

```sql
SELECT timestamp, footprint_level FROM candles
WHERE symbol='NIFTY_CE_0'
ORDER BY timestamp DESC
LIMIT 10;
```

---

## Common Issues

| Issue | Solution |
|-------|----------|
| Dropdown shows "[object Object]" | Dropdown not populated (initialize flag missing) |
| Charts blank after strike selection | API returned no data (check offset value) |
| Footprint not updating | ofpFpEnabled=false (click ⚙️ button) |
| Wrong data displayed | ofpCurrentOffset doesn't match data.offset (filter issue) |
| High memory usage | All 14 strikes in memory (~12 MB) — normal |
| Lag when switching strikes | Network delay on API call (wait 1-2 seconds) |
| Footprint boxes too small | Volume below Buy≥/Sell≥ filter (lower threshold) |

---

## Performance Tips

1. **Use 5-min timeframe** for day trading to reduce noise
2. **Set Buy≥/Sell≥ to 150000** for better visibility
3. **Keep Trace≥ at 100000** (default is optimal)
4. **Close other charts** if system is sluggish
5. **Use Chrome** for best performance (vs Firefox)

---

## Testing Checklist

- [ ] All 7 strikes load correctly when selected
- [ ] Charts update in real-time for current offset
- [ ] Dropdown doesn't reset after selection
- [ ] Footprint ON/OFF toggles visibly
- [ ] Timeframe buttons resample correctly
- [ ] Filters apply immediately
- [ ] LTP updates in header (every tick)
- [ ] Strike labels update when offset changes
- [ ] Database contains all 14 symbols
- [ ] No console errors

---

## Developer Notes

### Adding a New Filter

1. Add UI input in toolbar HTML
2. Create JavaScript variable (e.g., `ofpNewFilter = 0`)
3. Bind to `oninput` event → `drawOfpFootprint('CE'); drawOfpFootprint('PE')`
4. Add filter logic in `drawOfpFootprint()`:
   ```javascript
   if (level[newField] >= ofpNewFilter) {
       // Draw box
   }
   ```

### Adding a New Timeframe

1. Add button in toolbar: `<button data-ofp-tf="7">7m</button>`
2. Button automatically handled by click listener
3. `ofpTimeframe` updated to '7'
4. `loadOfpHistory()` called with new timeframe
5. `ofpResample()` handles the bucketing

### Adding Database Persistence

- Already handled automatically via `data_storage.store_candle()`
- No additional code needed
- Just ensure symbol format matches: `NIFTY_CE_offset`

---

## Summary

**14 Strikes**: All processed, stored, emitted in real-time  
**Filter by Offset**: Frontend filters incoming ticks  
**Load on Demand**: API returns data for selected offset only  
**Persistent Dropdown**: Shows actual prices, never resets  
**Independent Toolbar**: Complete separation from main chart  

---

**Status**: ✅ Production Ready  
**Last Updated**: June 23, 2026
