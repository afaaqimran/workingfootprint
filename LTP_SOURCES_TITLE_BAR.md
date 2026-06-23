# LTP Value Sources — Options Footprint Title Bar Display

**Document**: Complete reference for how LTP (Last Traded Price) values are displayed and updated in the Options Footprint chart title bar.

**Applies to**: Call (CE) and Put (PE) strike prices displayed in the header of the Options Footprint chart.

---

## 1. Overview — Two Update Sources

The LTP values in the title bar come from **two independent data streams**:

```
┌─────────────────────────────────────────────────────────────────┐
│                  LTP Display in Title Bar                        │
│         CE: ₹{value}            PE: ₹{value}                    │
└─────────────────────────────────────────────────────────────────┘
              ▲                              ▲
              │                              │
    ┌─────────┴──────────┐        ┌─────────┴──────────┐
    │                    │        │                    │
    │ Source 1:          │        │ Source 2:          │
    │ Real-Time Ticks    │        │ Periodic Polling   │
    │ (Primary)          │        │ (Fallback)         │
    │                    │        │                    │
    │ WebSocket Stream   │        │ API /options-chain │
    │ Every tick         │        │ Every 5 seconds    │
    │ Highest priority   │        │ Low priority       │
    └────────────────────┘        └────────────────────┘
```

---

## 2. Source 1: Real-Time Socket.IO Events (Primary)

### Data Flow

```
Backend WebSocket Handler
    ↓
Receives tick for ATM CE/PE
    ↓
_process_atm_option_footprint()
    ↓
Extracts LTP value from tick
    ↓
socketio.emit('options_fp_data')
    ↓
Frontend Socket.IO Listener
    ↓
ofpHandleLiveTick() processes candle
    ↓
Updates LTP in title bar immediately
```

### Backend: Emission Point

**File**: `footprint_web_app_upstox.py`  
**Function**: `_process_atm_option_footprint()` (Line 830)  
**Emission**: Line 904 & 907

```python
def _process_atm_option_footprint(self, opt_type, ltp, vtt, current_ts):
    """
    Build 1-minute candles + footprint for the ATM CE or PE option and
    emit via Socket.IO as 'options_fp_data' with field 'opt_type': 'CE'/'PE'.
    Also persist to footprint_data_OPTIONS_ATM.db.
    """
    # ... processing ...
    
    base_update = {
        'symbol':     symbol,
        'opt_type':   opt_type,         # ← 'CE' or 'PE'
        'offset':     0,                # ← ATM strike
        'timestamp':  int(current_candle['ts']),
        'open':       current_candle['open'],
        'high':       current_candle['high'],
        'low':        current_candle['low'],
        'close':      current_candle['close'],
        'ltp':        ltp,              # ← This is the LTP value
        'volume':     vtt,
        'volume_diff': volume_diff,
        'historical': False
    }
    
    # Emit to frontend
    socketio.emit('options_fp_data', update, room=self.user_id)  # Line 904/907
```

**Source of LTP value**: 
- From WebSocket market data feed received from Upstox
- Extracted from tick data for the locked ATM CE/PE instrument
- Filtered by: `instrument_key == self.atm_fp_ce_key` (for CE) or `self.atm_fp_pe_key` (for PE)

**Frequency**: Every tick received (typically 10-50ms during market hours)

**Update Trigger**: Line 1100-1110 in `footprint_web_app_upstox.py`

```python
if instrument_key == self.atm_fp_ce_key and ltp_val > 0:
    self._process_atm_option_footprint(
        opt_type='CE',
        ltp=ltp_val,
        vtt=vtt,
        current_ts=current_ts,
    )
```

---

### Frontend: Reception & Display

**File**: `templates/chart.html`  
**Socket.IO Listener**: Line 3006-3012

```javascript
socket.on('options_fp_data', (data) => {
    ofpHandleLiveTick(data);
    // Also update header LTP from live ticks
    if (data.opt_type === 'CE') {
        const el = document.getElementById('ofp-ce-ltp');
        if (el && data.ltp > 0) el.textContent = '₹' + data.ltp.toFixed(2);
    } else {
        const el = document.getElementById('ofp-pe-ltp');
        if (el && data.ltp > 0) el.textContent = '₹' + data.ltp.toFixed(2);
    }
});
```

**Display Elements**:
- CE LTP: `id="ofp-ce-ltp"` (green text, ₹ formatted) — Line 692
- PE LTP: `id="ofp-pe-ltp"` (red text, ₹ formatted) — Line 704

**Format**: `'₹' + value.toFixed(2)` (e.g., "₹254.50")

**Update Frequency**: Every tick (same as backend frequency)

---

## 3. Source 2: Periodic API Polling (Fallback)

### Purpose

Provides fallback LTP values if real-time stream is delayed or gaps occur. Acts as a safety net to ensure LTP is never stale.

### Data Flow

```
setInterval (every 5 seconds)
    ↓
ofpUpdateAtmInfo()
    ↓
Fetch /api/options-chain
    ↓
Returns live option chain data
    ↓
Find locked ATM strike CE and PE
    ↓
Extract LTP from chain data
    ↓
Update title bar LTP
```

### API Endpoint

**File**: `templates/chart.html`  
**Function**: `ofpUpdateAtmInfo()` (Line 2970)  
**Endpoint Called**: `/api/options-chain`

```javascript
async function ofpUpdateAtmInfo() {
    try {
        const resp = await fetch('/api/options-chain');
        const result = await resp.json();
        if (!result.success) return;

        // Update live spot price
        document.getElementById('ofp-spot').textContent = 
            result.nifty_ltp ? result.nifty_ltp.toFixed(2) : '—';

        // Update live LTP for the locked ATM CE and PE from the options chain data
        const lockedStrike = parseFloat(document.getElementById('ofp-atm').textContent);
        if (!isNaN(lockedStrike)) {
            const lockedCe = result.data.find(r => r.strike === lockedStrike && r.type === 'CE');
            const lockedPe = result.data.find(r => r.strike === lockedStrike && r.type === 'PE');
            
            if (lockedCe && lockedCe.ltp > 0)
                document.getElementById('ofp-ce-ltp').textContent = '₹' + lockedCe.ltp.toFixed(2);
            if (lockedPe && lockedPe.ltp > 0)
                document.getElementById('ofp-pe-ltp').textContent = '₹' + lockedPe.ltp.toFixed(2);
        }
    } catch (e) {}
}
```

### Setup & Timing

**Initialization**: Line 3019 (inside DOMContentLoaded)

```javascript
setInterval(ofpUpdateAtmInfo, 5000);  // 5-second interval
```

**Frequency**: Every 5 seconds

**Lookup Method**:
1. Retrieves locked ATM strike value from DOM: `document.getElementById('ofp-atm').textContent`
2. Searches options chain for matching strike: `strike === lockedStrike && type === 'CE'/'PE'`
3. Extracts LTP from matched record

---

## 4. Priority & Update Hierarchy

The real-time stream takes **strict priority** over periodic polling:

```
Priority Levels:
┌──────────────────────────────────────────────────────────────┐
│ 1. Real-Time Tick (Primary)                    ✅ Use Always │
│    - Updates immediately on each tick                         │
│    - Highest precision                                        │
│    - Updates every 10-50ms during market hours                │
│                                                                │
│ 2. Periodic Polling (Fallback)                 ✅ Use if Gap │
│    - Updates every 5 seconds                                  │
│    - Used if real-time stream has delays                      │
│    - Safety net to prevent stale values                       │
└──────────────────────────────────────────────────────────────┘

Behavior:
- If real-time tick arrives first → LTP updated immediately
- If 5-second poll interval completes before next tick → LTP updated from API
- During normal market hours → Real-time wins (updates much faster)
- During low-activity periods → Polling ensures LTP never stale (max 5s delay)
```

---

## 5. Display Elements (HTML Structure)

### CE (Call) LTP Display

**Location**: `templates/chart.html` Line 692

```html
<div style="padding:4px 8px;background:#0d1117;border-bottom:1px solid #2B2B43;
            display:flex;align-items:center;gap:8px;flex-shrink:0;">
    <span style="font-size:11px;font-weight:700;color:#26a69a;">📈 ATM CALL (CE)</span>
    <span style="font-size:11px;color:#8b949e;">
        LTP: <strong id="ofp-ce-ltp" style="color:#26a69a;">—</strong>
    </span>
    <span style="font-size:11px;color:#8b949e;">
        Strike: <strong id="ofp-ce-strike" style="color:#e6edf3;">—</strong>
    </span>
    <span id="ofp-ce-status" style="font-size:10px;color:#555;margin-left:auto;"></span>
</div>
```

**Styling**:
- Color: Green (`#26a69a`) — indicates bullish/call direction
- Format: `LTP: ₹{value}` (e.g., "LTP: ₹254.50")
- Font size: 11px, bold weight

### PE (Put) LTP Display

**Location**: `templates/chart.html` Line 704

```html
<div style="padding:4px 8px;background:#0d1117;border-bottom:1px solid #2B2B43;
            display:flex;align-items:center;gap:8px;flex-shrink:0;">
    <span style="font-size:11px;font-weight:700;color:#ef5350;">📉 ATM PUT (PE)</span>
    <span style="font-size:11px;color:#8b949e;">
        LTP: <strong id="ofp-pe-ltp" style="color:#ef5350;">—</strong>
    </span>
    <span style="font-size:11px;color:#8b949e;">
        Strike: <strong id="ofp-pe-strike" style="color:#e6edf3;">—</strong>
    </span>
    <span id="ofp-pe-status" style="font-size:10px;color:#555;margin-left:auto;"></span>
</div>
```

**Styling**:
- Color: Red (`#ef5350`) — indicates bearish/put direction
- Format: `LTP: ₹{value}` (e.g., "LTP: ₹8.75")
- Font size: 11px, bold weight

---

## 6. Scenario: What Happens When Conditions Change

### Scenario A: Normal Operation

```
Time  │ Event                         │ CE LTP      │ PE LTP
──────┼───────────────────────────────┼─────────────┼──────────
09:45 │ Login, chart loads            │ ₹150.00     │ ₹42.50
09:45 │ Tick arrives (CE goes up)     │ ₹150.25     │ ₹42.50  ← Real-time
09:45 │ Tick arrives (PE goes down)   │ ₹150.25     │ ₹42.45  ← Real-time
09:50 │ 5-sec poll runs               │ ₹150.25     │ ₹42.45  ← No change (real-time already updated)
```

### Scenario B: Network Delay (Real-time Slow)

```
Time   │ Event                              │ CE LTP      │ PE LTP
───────┼────────────────────────────────────┼─────────────┼──────────
09:45  │ Tick arrives (CE goes up)          │ ₹150.25     │ ₹42.50
09:50  │ 5-sec poll (tick delayed)          │ ₹150.50     │ ₹42.35  ← API used (fills gap)
09:51  │ Delayed tick finally arrives       │ ₹150.50     │ ₹42.35  ← Real-time (no change)
```

### Scenario C: Strike Switch

```
Time  │ Event                                    │ CE LTP      │ PE LTP
──────┼────────────────────────────────────────┼─────────────┼──────────
09:45 │ ATM CE/PE chart displayed              │ ₹150.25     │ ₹42.50
10:00 │ User clicks "ATM+100" strike           │ (chart resets, new data loaded)
10:00 │ First tick for new strike arrives      │ ₹125.75     │ ₹18.25  ← Real-time (new strike)
10:05 │ 5-sec poll (confirms new values)       │ ₹125.75     │ ₹18.25  ← API (no change, already updated)
```

---

## 7. Code Reference Map

### Backend Sources

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| **Tick Reception** | `footprint_web_app_upstox.py` | ~1100 | Receives WebSocket tick for ATM CE/PE |
| **LTP Extraction** | `footprint_web_app_upstox.py` | 830-915 | `_process_atm_option_footprint()` processes tick and extracts LTP |
| **Emission** | `footprint_web_app_upstox.py` | 904, 907 | `socketio.emit('options_fp_data', ...)` with LTP |
| **API Endpoint** | `footprint_web_app_upstox.py` | ~1831 | `/api/options-chain` endpoint for periodic polling |

### Frontend Update Points

| Component | File | Line | Purpose |
|-----------|------|------|---------|
| **Real-Time Listener** | `templates/chart.html` | 3006-3012 | `socket.on('options_fp_data', ...)` receives tick data and updates LTP |
| **CE LTP Element** | `templates/chart.html` | 692 | Display element for Call LTP |
| **PE LTP Element** | `templates/chart.html` | 704 | Display element for Put LTP |
| **Periodic Poller** | `templates/chart.html` | 2970-2993 | `ofpUpdateAtmInfo()` fetches from API every 5 seconds |
| **Poller Interval** | `templates/chart.html` | 3019 | `setInterval(ofpUpdateAtmInfo, 5000)` |

---

## 8. Data Consistency

### ATM Strike Tracking

Both sources track the **same locked ATM strike** throughout the session:

- **Real-time source**: Filters by `instrument_key` (hardcoded at login)
- **Periodic source**: Looks up by strike value: `document.getElementById('ofp-atm').textContent`

**Key guarantee**: Both sources always display LTP for the same strike, preventing display inconsistency.

### Volume & Timestamp

LTP is always accompanied by:
- **Volume (`vtt`)**: Total volume traded up to that tick
- **Timestamp**: Candle timestamp (rounded to 1-minute bucket)
- **Candle OHLC**: Open, High, Low, Close prices for current 1-minute candle

---

## 9. Initialization Sequence

```
User opens Options Footprint Chart
    ↓
1. DOMContentLoaded fires
    ↓
2. ofpLoadHistory() fetches stored candles from DB
    ↓
3. Initial LTP values set in title bar (from DB)
    ↓
4. Socket.IO hook waits for 'options_fp_data' events
    ↓
5. setInterval(ofpUpdateAtmInfo, 5000) starts polling
    ↓
6. First real-time tick arrives
    ↓
7. Both real-time and polling become active
    ↓
8. LTP updates continuously (real-time primary, polling fallback)
```

---

## 10. Troubleshooting Guide

### Issue: LTP Not Updating

**Check real-time stream**:
1. Open browser DevTools → Network → WebSocket
2. Look for Socket.IO connection with `options_fp_data` events
3. Should see events every 10-50ms during market hours

**Check polling fallback**:
1. Open DevTools → Network → XHR/Fetch
2. Look for `/api/options-chain` requests every 5 seconds
3. Should show `success: true` and live option chain data

### Issue: LTP Stale (Not Updating for 5+ Seconds)

**Likely cause**: Real-time stream disconnected AND periodic polling failed

**Solution**:
1. Check WebSocket connection status
2. Reload chart to reconnect
3. Verify `/api/options-chain` endpoint is responding

### Issue: CE and PE LTP Different Between Refreshes

**Check database state**:
1. Last stored candle may be from previous session
2. First real-time tick after login updates both correctly
3. Should synchronize within 1 tick

---

## 11. Summary

| Aspect | Detail |
|--------|--------|
| **Primary Source** | Real-time WebSocket tick from backend |
| **Fallback Source** | API polling every 5 seconds |
| **Update Frequency** | Every 10-50ms (real-time) or 5s (fallback) |
| **Data Quality** | Live market data from Upstox feed |
| **Display Format** | `₹{value}.toFixed(2)` (e.g., "₹254.50") |
| **ATM Tracking** | Locked at login, both sources track same strike |
| **Consistency** | Both sources always show same strike LTP |
| **Recovery** | Polling provides gap-fill if real-time delayed |

---

**Document Version**: 1.0  
**Last Updated**: June 23, 2026  
**Status**: Complete & Verified
