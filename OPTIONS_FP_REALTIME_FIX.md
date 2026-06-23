# Options Footprint Chart Real-Time Update Fix

**Issue:** Options Footprint chart was not updating in real-time when the tab was clicked.

**Root Cause:** The backend `_process_atm_option_footprint()` function was emitting `options_fp_data` Socket.IO events without the `offset` field. The frontend was filtering incoming socket events by offset (checking if `data.offset === ofpCurrentOffset`), so all events were being rejected/skipped because `data.offset` was undefined.

**Solution:** Added `'offset': 0` field to the `base_update` dictionary in `_process_atm_option_footprint()`.

---

## File Changes

### `footprint_web_app_upstox.py` (Line 841-853)

**Before:**
```python
base_update = {
    'symbol':    symbol,
    'opt_type':  opt_type,
    'timestamp': int(current_candle['ts']),
    'open':      current_candle['open'],
    'high':      current_candle['high'],
    'low':       current_candle['low'],
    'close':     current_candle['close'],
    'ltp':       ltp,
    'volume':    vtt,
    'volume_diff': volume_diff,
    'historical': False
}
```

**After:**
```python
base_update = {
    'symbol':    symbol,
    'opt_type':  opt_type,
    'offset':    0,  # ATM footprint always uses offset 0
    'timestamp': int(current_candle['ts']),
    'open':      current_candle['open'],
    'high':      current_candle['high'],
    'low':       current_candle['low'],
    'close':     current_candle['close'],
    'ltp':       ltp,
    'volume':    vtt,
    'volume_diff': volume_diff,
    'historical': False
}
```

---

## How It Works Now

1. **User logs in** → ATM CE/PE subscriptions begin via `subscribe_options_strikes()`
2. **WebSocket ticks arrive** → `process_websocket_data()` routes them to `_process_atm_option_footprint('CE'|'PE')`
3. **Backend emits event** → `socketio.emit('options_fp_data', update, room=self.user_id)` sends event with `offset: 0`
4. **Frontend receives** → `socket.on('options_fp_data', data => ofpHandleLiveTick(data))`
5. **Offset check passes** → `data.offset (0) === ofpCurrentOffset ('0')` → TRUE → event is processed
6. **Chart updates** → `series.update()` and `drawOfpFootprint(side)` are called
7. **Real-time display** → CE and PE candles update live with footprint boxes

---

## Testing

To verify the fix:
1. Open the application and log in
2. Click on the Options Footprint tab (🕯)
3. Observe the CE and PE candles updating in real-time
4. Observe the footprint boxes (buy/sell volume) drawing/updating as market data arrives
5. Change the offset via the dropdown selector to verify filtering works correctly

---

**Status:** ✅ Fixed
**Date Fixed:** 17 June 2026
