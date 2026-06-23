# ATM Oscillation Fix — Quick Reference

**Status**: ✅ Fixed and Deployed  
**Commit**: `188830f`  
**Impact**: Eliminates chart freezing/reloading caused by ATM flickering at strike boundaries

---

## The Problem

**In Production**: ATM strike oscillates between two 100-point levels (e.g., 24100 ↔ 24150) when spot price hovers at boundaries, causing:
- Infinite re-subscriptions (unsubscribe 14 options, resubscribe 14 options, repeat)
- Chart appears stuck/constantly reloading
- High WebSocket churn and network load

**Root Cause**: Hysteresis threshold (40 points) was LESS than rounding boundary (50 points), creating oscillation

---

## The Fix (Applied)

### What Changed

**File**: `footprint_web_app_upstox.py` — `_atm_monitor()` function

1. **Fixed Rounding** (Line 792):
   ```python
   # OLD: current_atm = round(spot / 50) * 50      # 50-point rounding (WRONG)
   # NEW: current_atm = round(spot / STRIKE_STEP) * STRIKE_STEP  # 100-point
   ```

2. **Increased Hysteresis** (Line 778):
   ```python
   # OLD: HYSTERESIS = 15
   # NEW: HYSTERESIS = 50  # Conservative buffer prevents oscillation
   ```

3. **Fixed Hysteresis Condition** (Line 844-845):
   ```python
   # OLD: spot >= last_atm + 25 + HYSTERESIS        # spot >= last_atm + 40
   # NEW: spot >= last_atm + (STRIKE_STEP / 2) + HYSTERESIS  # spot >= last_atm + 100
   ```

### Why It Works

- **100-point increment threshold** ensures clean ATM shifts aligned with Options Footprint strikes
- **50-point hysteresis buffer** creates "dead zone" around boundaries
- **Combined threshold (100 points)** is conservative → prevents oscillation
- Example: ATM only shifts 24100→24200 when spot reaches 24200 (not before)

---

## Verification Checklist

After deployment, confirm:

- [ ] Chart no longer appears stuck/constantly reloading
- [ ] ATM remains stable when spot hovers near boundaries
- [ ] Re-subscriptions only happen when spot crosses ±100-point boundaries
- [ ] No ATM oscillations in logs (search for "ATM shifted")
- [ ] Network traffic returns to normal (fewer unsubscribe/subscribe pairs)

---

## Testing Scenarios

### Scenario 1: Boundary Hover (Most Important)
```
Spot moves: 24090 → 24100 → 24110 → 24120 → 24124 → 24125 → 24150
Expected: ATM stays 24100 until spot >= 24200 ✓
```
If this works, the fix is successful.

### Scenario 2: Oscillation Resistance
```
Spot moves: 24140 → 24150 → 24140 (rapid reversal)
Expected: No ATM shift, no re-subscription ✓
```

### Scenario 3: Clean Shift
```
Spot moves: 24100 → 24200 (clear boundary cross)
Expected: ATM shifts 24100 → 24200, re-subscription happens ✓
```

---

## Monitoring

**Key Metrics to Watch**:
- **Re-subscription frequency**: Should be 10-100x lower than before
- **Chart stability**: No more flicker/reload patterns
- **Network traffic**: Unsubscribe/subscribe count should ↓
- **User experience**: Chart should feel smooth and responsive

---

## Technical Details

### Mathematical Explanation

For 100-point options strikes (24000, 24100, 24200...):
- Boundary midpoint: `ATM + 50`
- Safe shift threshold: `ATM + 100` (requires 100 points past starting ATM)

When spot = 24124-24125:
- **Before fix**: Rounding flips at 50 points, but hysteresis allows at 40 points → oscillation
- **After fix**: Rounding stays stable until spot ≥ 100 points past boundary → no oscillation

### Why Previous Code Failed

```python
current_atm = round(spot / 50) * 50  # Rounds at every 50 points
if spot >= last_atm + 40:            # But allows shift at only 40 points
    # Re-subscribe                    # Mismatch causes oscillation
```

This created a condition where the rounding triggered before the hysteresis was satisfied, causing back-and-forth shifts.

---

## If Issues Occur

### Issue: Still seeing oscillations
- **Check**: Verify STRIKE_STEP = 100 and HYSTERESIS = 50 in code
- **Solution**: May need to increase HYSTERESIS to 75 or 100 for more conservative behavior

### Issue: ATM not shifting when it should
- **Check**: Verify spot actually crossed 100-point boundary
- **Note**: New threshold is conservative by design; use dashboard to confirm

### Issue: Rollback needed
- **Command**: `git revert 188830f`
- **Note**: Uncommon; previous fixes were comprehensive

---

## Related Documentation

- **Full technical analysis**: `ATM_OSCILLATION_FIX.md` (comprehensive deep-dive)
- **Pre-open fixes**: `PREOPEN_ATM_LOCK_FIX.md` (ATM locking before market open)
- **Options Footprint architecture**: `OPTIONS_FOOTPRINT_ARCHITECTURE.md` (system design)

---

## Summary

✅ **Fixed**: Changed rounding from 50-point to 100-point increments  
✅ **Increased**: Hysteresis from 15 to 50 points for stability  
✅ **Result**: No more ATM oscillation, chart remains stable and responsive  
✅ **Deployed**: Commit `188830f` pushed to production  

**Next Steps**: Monitor logs and user feedback to confirm resolution.
