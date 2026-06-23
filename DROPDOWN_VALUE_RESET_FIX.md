# Options Footprint Dropdown Value Reset - Fix

**Issue:** When clicking on a strike price in the dropdown, the chart didn't update and always showed ATM data. The dropdown value didn't change/stay selected.

---

## Root Cause

The `populateStrikeDropdown()` function was being called **every time** `loadOfpHistory()` was executed. Here's what happened:

### Problem Flow:

1. User opens Options Footprint tab
2. `initOptFPCharts()` calls `loadOfpHistory('CE')` 
3. Inside `loadOfpHistory('CE')`:
   - Fetches CE data
   - Calls `populateStrikeDropdown()` 
   - Sets dropdown value to `'0'` (ATM)
4. `initOptFPCharts()` also calls `loadOfpHistory('PE')`
5. Inside `loadOfpHistory('PE')`:
   - Fetches PE data
   - **Calls `populateStrikeDropdown()` AGAIN**
   - **Resets dropdown value to `'0'` again!** ❌
6. User selects offset "100" from dropdown
7. `switchOfpStrike()` sets `ofpCurrentOffset = '100'`
8. `switchOfpStrike()` calls `loadOfpHistory('CE')`
9. Inside `loadOfpHistory('CE')`:
   - Fetches CE data for offset 100
   - **Calls `populateStrikeDropdown()` AGAIN**
   - **Resets dropdown value back to `'0'`!** ❌❌
10. User sees the dropdown is back at ATM and chart shows ATM data

**Result:** The dropdown value always resets to ATM immediately after being selected, so users couldn't select any other offset.

---

## Solution

Added a flag `ofpDropdownInitialized` to ensure `populateStrikeDropdown()` is only called **once**, during initial setup.

### Code Changes (templates/chart.html):

#### Change 1: Add flag (line 2484):
```javascript
let ofpDropdownInitialized = false;       // Flag to prevent repopulating dropdown
```

#### Change 2: Protect populateStrikeDropdown() call (lines 2793-2797):
**Before:**
```javascript
// Populate dropdown with actual strike prices (only do this once)
if (side === 'CE') {
    populateStrikeDropdown();
}
```

**After:**
```javascript
// Populate dropdown with actual strike prices (only do this once, ever)
if (!ofpDropdownInitialized) {
    ofpDropdownInitialized = true;
    populateStrikeDropdown();
}
```

---

## How It Works Now

### Correct Flow:

1. User opens Options Footprint tab
2. `initOptFPCharts()` calls `loadOfpHistory('CE')`
3. Inside `loadOfpHistory('CE')`:
   - Fetches CE data
   - Checks: `!ofpDropdownInitialized` ? → TRUE
   - Sets `ofpDropdownInitialized = true`
   - Calls `populateStrikeDropdown()` ✅
   - Sets dropdown to `'0'` (ATM)
4. `initOptFPCharts()` calls `loadOfpHistory('PE')`
5. Inside `loadOfpHistory('PE')`:
   - Fetches PE data
   - Checks: `!ofpDropdownInitialized` ? → FALSE (already initialized)
   - **Skips `populateStrikeDropdown()`** ✅
   - Dropdown stays at `'0'`
6. User selects offset "100" from dropdown
7. `switchOfpStrike()` sets `ofpCurrentOffset = '100'`
8. `switchOfpStrike()` calls `loadOfpHistory('CE')`
9. Inside `loadOfpHistory('CE')`:
   - Fetches CE data for offset 100
   - Checks: `!ofpDropdownInitialized` ? → FALSE (already initialized)
   - **Skips `populateStrikeDropdown()`** ✅
   - Dropdown **stays at "100"** ✅
   - Chart updates with offset 100 data ✅
10. User sees correct offset selected and chart showing correct data ✅

---

## Debugging Features Added

Also added console logging to help debug any future issues:

### switchOfpStrike():
```
📊 Dropdown changed: newOffset=100, ofpCurrentOffset=0
✅ ofpCurrentOffset updated to: 100
🔄 Loading history for offset 100
```

### loadOfpHistory():
```
📡 Fetching CE data: /api/options-footprint-data?type=CE&offset=100&days=1
📥 CE response: {success: true, data: [...], offset: 100, ...}
📊 Loaded 15 candles for CE, offset=100
```

### populateStrikeDropdown():
```
📋 Populating dropdown with ATM=24500
  Added option: offset=-300, label=24200
  Added option: offset=-200, label=24300
  Added option: offset=-100, label=24400
  ...
✅ Dropdown populated, default value set to '0'
```

Open browser console (F12 → Console tab) to see these logs.

---

## Testing the Fix

1. **Start the updated server**
2. **Log in** and open Options Footprint tab (🕯)
3. **Verify initial state:**
   - Dropdown shows ATM strike (e.g., "24500")
   - CE and PE charts display ATM data ✅
4. **Select ATM+100** from dropdown:
   - Dropdown value changes to "24600" ✅
   - Value stays selected (doesn't reset) ✅
   - CE and PE charts update with ATM+100 data ✅
   - Charts update in real-time as new ticks arrive ✅
5. **Select ATM-200** from dropdown:
   - Dropdown value changes to "24300" ✅
   - Value stays selected ✅
   - Charts show ATM-200 data ✅
6. **Switch back to ATM:**
   - Dropdown value changes back to "24500" ✅
   - All data updates correctly ✅

---

## Browser Console

To verify the fix is working, open browser Developer Tools (F12) and go to the Console tab. You should see:

```
📋 Populating dropdown with ATM=24500
  Added option: offset=-300, label=24200
  ...
  Added option: offset=300, label=24800
✅ Dropdown populated, default value set to '0'
📡 Fetching CE data: /api/options-footprint-data?type=CE&offset=0&days=1
📥 CE response: {success: true, data: [...]}
📊 Loaded X candles for CE, offset=0
📡 Fetching PE data: /api/options-footprint-data?type=PE&offset=0&days=1
📥 PE response: {success: true, data: [...]}
📊 Loaded Y candles for PE, offset=0
```

Then when you select a different offset:
```
📊 Dropdown changed: newOffset=100, ofpCurrentOffset=0
✅ ofpCurrentOffset updated to: 100
🔄 Loading history for offset 100
📡 Fetching CE data: /api/options-footprint-data?type=CE&offset=100&days=1
📥 CE response: {success: true, data: [...], offset: 100}
📊 Loaded X candles for CE, offset=100
```

---

**Status:** ✅ **FIXED** - Dropdown selection now works correctly and charts display the selected strike offset!

**Date Fixed:** 17 June 2026
