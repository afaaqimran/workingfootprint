# Options Footprint Dropdown Strike Selection - Fix

**Issue:** When changing the strike offset via the dropdown (ATM+100, ATM-100, etc.), the CE and PE charts were not displaying data or updating in real-time.

---

## Root Cause

The `_process_all_strike_footprints()` function was **only storing data to the database** for all 14 strike combinations but **NOT emitting real-time Socket.IO events**.

This meant:
- **ATM (offset 0):** ✅ Data emitted in real-time via `_process_atm_option_footprint()` 
- **Other offsets (±100, ±200, ±300):** ❌ Data only stored to DB, never emitted

**Result:** When users selected non-ATM offsets from the dropdown, the charts would load historical data but wouldn't update in real-time because no Socket.IO events were being sent.

---

## Solution

Updated `_process_all_strike_footprints()` to emit real-time Socket.IO events for all strike offsets, not just store to the database.

### Code Change (footprint_web_app_upstox.py, lines 952-964):

**Before:**
```python
if footprint_levels:
    for level in footprint_levels:
        update = base_update.copy()
        update['footprint_level'] = level
        # Only emit if this is the current selected offset (user UI choice)
        # The selection is in a client-side variable, but we store all data anyway
        data_storage.store_candle(update, '1')
else:
    data_storage.store_candle(base_update, '1')
```

**After:**
```python
if footprint_levels:
    for level in footprint_levels:
        update = base_update.copy()
        update['footprint_level'] = level
        # Emit for real-time chart updates (not just store to DB)
        socketio.emit('options_fp_data', update, room=self.user_id)
        data_storage.store_candle(update, '1')
else:
    # Emit even when no footprint levels (for candle updates)
    socketio.emit('options_fp_data', base_update, room=self.user_id)
    data_storage.store_candle(base_update, '1')
```

---

## Data Flow Now

### Before (Broken):
```
WebSocket tick for ATM+100 CE
    ↓
process_websocket_data()
    ↓
_process_all_strike_footprints('CE', offset=100, ltp=...)
    ↓
Store to DB only ❌
    ↓
No Socket.IO event emitted ❌
    ↓
Frontend never updates real-time ❌
```

### After (Fixed):
```
WebSocket tick for ATM+100 CE
    ↓
process_websocket_data()
    ↓
_process_all_strike_footprints('CE', offset=100, ltp=...)
    ↓
socketio.emit('options_fp_data', {..., offset: 100, opt_type: 'CE'})  ✅
    ↓
Store to DB ✅
    ↓
Frontend receives event via ofpHandleLiveTick(data)
    ↓
Check: data.offset (100) === ofpCurrentOffset (user selection)?
    ↓
If YES: Update charts and footprint in real-time ✅
```

---

## How It Works Now

### Scenario: User selects ATM+100 from dropdown

1. **User clicks dropdown** → selects "24600" (ATM + 100)
2. **switchOfpStrike()** called:
   - Sets `ofpCurrentOffset = '100'`
   - Calls `loadOfpHistory('CE')` and `loadOfpHistory('PE')`
3. **loadOfpHistory()** fetches from `/api/options-footprint-data?type=CE&offset=100&days=1`:
   - Retrieves any historical candles from DB for that offset
   - Displays them on the chart
4. **Real-time WebSocket ticks arrive** for ATM+100 CE contract:
   - Backend calls `_process_all_strike_footprints('CE', offset=100, ...)`
   - **NOW:** Emits `socketio.emit('options_fp_data', {..., offset: 100})`
   - Frontend receives event
   - `ofpHandleLiveTick()` checks: `data.offset (100) === ofpCurrentOffset ('100')` ✅ TRUE
   - Chart candles update in real-time ✅
   - Footprint boxes drawn ✅

---

## Complete Fix Summary

**Three fixes were required for full functionality:**

| Fix | Location | What | Why |
|-----|----------|------|-----|
| **Fix 1** | `_process_atm_option_footprint()`, line 844 | Added `'offset': 0` field to emitted events | Frontend filters by offset; without this field, offset was undefined |
| **Fix 2** | `process_websocket_data()`, lines 1052-1063 | Added code to check for ATM CE/PE keys and call `_process_atm_option_footprint()` | ATM footprint was never being processed/emitted |
| **Fix 3** | `_process_all_strike_footprints()`, lines 952-964 | Added `socketio.emit()` calls for all strike offsets | Non-ATM offsets were only stored to DB, never emitted for real-time updates |

---

## Testing the Fix

1. **Start the updated server**
2. **Log in** and open the Options Footprint tab (🕯)
3. **Verify ATM (offset 0):**
   - Charts display and update in real-time ✅
4. **Select ATM+100** from dropdown:
   - Charts load data from DB ✅
   - CE and PE candles update in real-time ✅
   - Footprint boxes appear and update ✅
5. **Select ATM-200** from dropdown:
   - Same behavior as ATM+100 ✅
6. **Switch back to ATM:**
   - All ATM data still updates in real-time ✅

---

## Database Storage

All 14 strike combinations continue to be stored to the database regardless of user UI selection:
- `NIFTY_CE_-300` through `NIFTY_CE_300` (7 CE offsets)
- `NIFTY_PE_-300` through `NIFTY_PE_300` (7 PE offsets)

This allows users to navigate historical data for any offset, not just the currently selected one.

---

**Status:** ✅ **FIXED** - All dropdown offsets now update in real-time with live candle data and footprints

**Date Fixed:** 17 June 2026
