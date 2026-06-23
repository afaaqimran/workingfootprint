# Strike Rounding Verification Report
**Date**: June 17, 2026  
**Status**: ✅ VERIFIED - 100pt rounding is ONLY for Options Footprint chart

## Summary
The implementation correctly applies **100-point strike rounding ONLY to the Options Footprint chart** via `subscribe_options_strikes()`. All other tabs use **50-point rounding** for ATM calculation as expected.

---

## Detailed Verification

### 1. Options Footprint Chart (Options FP Tab - 🕯)
**Status**: ✅ Uses 100-point rounding ONLY for this tab

- **Function**: `subscribe_options_strikes()` (Line 575)
- **Strike Step**: `strike_step = 100` (Line 595)
- **ATM Calculation**: `atm_strike = round(atm_ltp / strike_step) * strike_step` (Line 629)
- **Database**: Stores in `footprint_data_OPTIONS_ATM.db` with 14 symbols (7 strikes × 2 types)
- **Subscribed Keys**: 14 total
  - CE: NIFTY_CE_-300, NIFTY_CE_-200, NIFTY_CE_-100, NIFTY_CE_0, NIFTY_CE_100, NIFTY_CE_200, NIFTY_CE_300
  - PE: NIFTY_PE_-300, NIFTY_PE_-200, NIFTY_PE_-100, NIFTY_PE_0, NIFTY_PE_100, NIFTY_PE_200, NIFTY_PE_300
- **Data Storage**: Current day only (no historical data)
- **Frontend**: Dropdown shows actual strike prices (e.g., 24200, 24300, 24400, 24500, 24600, 24700, 24800)

---

### 2. Other Tabs - All Use 50-Point Rounding

#### 2.1 Options Chain Tab (📈)
- **Function**: `get_options_chain()` (Line 1356)
- **ATM Calculation**: Uses subscribed options from `options_meta` (mixed 50pt strikes)
- **Note**: Does NOT use explicit rounding; uses strikes from subscription

#### 2.2 OI Tracker Tab (📊)
- **Function**: `get_oi_tracker()` (Line 1526)
- **ATM Calculation**: `atm_strike = round(nifty_spot / 50) * 50` (Line 1573) ✅
- **Rounding**: 50-point increment

#### 2.3 Volatility Skew Tab (📉)
- **Function**: `get_volatility_skew()` (Line 1589)
- **ATM Calculation**: `atm_strike = round(nifty_spot / 50) * 50` (Line 1607) ✅
- **Rounding**: 50-point increment

#### 2.4 Option Chain Full Tab (🔗)
- **Function**: `get_option_chain_full()` (Line 1690)
- **ATM Calculation**: `atm_strike = round(nifty_spot / 50) * 50` (Line 1722) ✅
- **Rounding**: 50-point increment

#### 2.5 TBA (Time-Based Analysis) Tab (⏱)
- **Function**: `get_tba_snapshot()` (Line 1783)
- **ATM Calculation**: `atm_strike = round(nifty_spot / 50) * 50` (Line 1804) ✅
- **Rounding**: 50-point increment

#### 2.6 Rate of Change (ROC) Tab (📈%)
- **Function**: `get_roc()` (Line 2178)
- **ATM Calculation**: `atm_strike = round(nifty_spot / 50) * 50` (Line 2268) ✅
- **Rounding**: 50-point increment

---

## Grep Verification Results

```
Line 629:  subscribe_options_strikes()     — 100pt (strike_step = 100)
Line 1573: get_oi_tracker()                — 50pt ✅
Line 1607: get_volatility_skew()           — 50pt ✅
Line 1722: get_option_chain_full()         — 50pt ✅
Line 1804: get_tba_snapshot()              — 50pt ✅
Line 2268: get_roc()                       — 50pt ✅
```

---

## Implementation Summary

| Feature | Strike Rounding | Status |
|---------|-----------------|--------|
| Options Footprint (🕯) | 100pt | ✅ Correct |
| Options Chain (📈) | Mixed (from subscribed 50pt) | ✅ Correct |
| OI Tracker (📊) | 50pt | ✅ Correct |
| Volatility Skew (📉) | 50pt | ✅ Correct |
| Option Chain Full (🔗) | 50pt | ✅ Correct |
| TBA (⏱) | 50pt | ✅ Correct |
| ROC (📈%) | 50pt | ✅ Correct |

---

## Conclusion

✅ **VERIFIED**: The codebase correctly implements:
- **100-point strike rounding ONLY for Options Footprint chart** via `subscribe_options_strikes()`
- **50-point ATM rounding for all other tabs** (OI Tracker, Volatility Skew, Option Chain Full, TBA, ROC)
- **Options Chain tab** uses strikes from subscription (which are 50pt for most cases)

**No changes needed.** Implementation is correct and matches user requirements.
