# Options Footprint Chart — Complete Documentation Index

## Documentation Files

### 📋 Main Analysis Documents

| File | Size | Purpose |
|------|------|---------|
| **BEHAVIOR_ANALYSIS_COMPLETE.md** | 19 KB | Master document with all findings and analysis |
| **OPTIONS_FOOTPRINT_BEHAVIOR.md** | 16 KB | Complete end-to-end behavior documentation |
| **OPTIONS_FOOTPRINT_ARCHITECTURE.md** | 19 KB | Architecture diagrams and component flows |
| **BEHAVIOR_SUMMARY.md** | 13 KB | High-level summary and workflows |
| **OPTIONS_FOOTPRINT_QUICK_REFERENCE.md** | 11 KB | Quick reference guide and code snippets |

### 📂 Related Documentation

| File | Purpose |
|------|---------|
| **APP_CONTEXT.md** | Overall application documentation |
| **VERIFICATION_REPORT.md** | Strike rounding verification (reference) |
| **OPTIONS_FP_COMPLETE_FIX_SUMMARY.md** | Complete fix summary (reference) |

---

## Quick Navigation

### For Understanding the System

1. **Start Here**: `BEHAVIOR_SUMMARY.md` (5-minute read)
2. **Deep Dive**: `OPTIONS_FOOTPRINT_BEHAVIOR.md` (20-minute read)
3. **Architecture**: `OPTIONS_FOOTPRINT_ARCHITECTURE.md` (15-minute read)

### For Coding/Debugging

1. **Find Code**: `OPTIONS_FOOTPRINT_QUICK_REFERENCE.md`
   - Search for function names
   - Get exact line numbers
   - See code snippets
   
2. **Understand Flow**: `OPTIONS_FOOTPRINT_ARCHITECTURE.md`
   - Data flow diagrams
   - Component interactions
   - Processing pipeline

3. **Check Details**: `OPTIONS_FOOTPRINT_BEHAVIOR.md`
   - Full implementation details
   - State management
   - API endpoints

### For Testing

1. Check: `BEHAVIOR_ANALYSIS_COMPLETE.md` → Verification Results section
2. Review: `BEHAVIOR_SUMMARY.md` → Verification Checklist
3. Follow: Step-by-step test procedures in each document

---

## Key Concepts

### Architecture

```
14 Strike Combinations
    (7 offsets × 2 types)
        ↓
All Processed in Parallel
        ↓
Real-Time Emission
        ↓
Frontend Filtering
        ↓
Display Per Offset
```

### Data Flow

```
WebSocket Tick
    ↓
Backend (Process all 14)
    ├─ Build candles
    ├─ Calculate footprint
    ├─ Store to DB
    └─ Emit Socket.IO
         ↓
Frontend Receives
    ├─ Filter by offset
    ├─ Update chart
    └─ Redraw footprint
```

### User Interaction

```
Select Strike
    ↓
Load Historical Data
    ↓
Display Charts
    ↓
Real-Time Updates (Filtered)
```

---

## File Usage Matrix

| Need | Read This | Section |
|------|-----------|---------|
| Overall understanding | BEHAVIOR_SUMMARY.md | Any section |
| Code location | QUICK_REFERENCE.md | Key Files section |
| Data structure | ARCHITECTURE.md | Database Schema |
| Real-time flow | BEHAVIOR.md | Real-Time Data Flow |
| API endpoint | QUICK_REFERENCE.md | Backend Processing |
| Frontend functions | QUICK_REFERENCE.md | Frontend Processing |
| Error handling | ARCHITECTURE.md | Error Handling |
| Performance | QUICK_REFERENCE.md | Performance Tips |
| Developer changes | QUICK_REFERENCE.md | Developer Notes |

---

## Key Sections by Topic

### Real-Time Processing

- **BEHAVIOR.md** → "Real-Time Data Flow" (detailed)
- **QUICK_REFERENCE.md** → "On Each WebSocket Tick" (code)
- **ARCHITECTURE.md** → "Data Processing Pipeline" (diagrams)

### Multi-Strike Support

- **SUMMARY.md** → "Multi-Strike Support" (overview)
- **BEHAVIOR.md** → "Multi-Strike Architecture" (detailed)
- **QUICK_REFERENCE.md** → "Strike Offset Mapping" (table)

### Frontend Display

- **ARCHITECTURE.md** → "Frontend Components" (diagram)
- **BEHAVIOR.md** → "Key Functions" (detailed)
- **QUICK_REFERENCE.md** → "Frontend Processing" (code flow)

### Database

- **QUICK_REFERENCE.md** → "Database Queries" (SQL examples)
- **ARCHITECTURE.md** → "Database Schema" (detailed schema)
- **BEHAVIOR.md** → "Data Storage" (persistence strategy)

### Toolbar Controls

- **QUICK_REFERENCE.md** → "Toolbar Controls" (reference)
- **BEHAVIOR.md** → "Toolbar Controls" (detailed explanation)
- **SUMMARY.md** → "Features" (overview)

---

## Important Line Numbers

### Backend (`footprint_web_app_upstox.py`)

- **214-217**: Subscribe to all 14 strikes
- **786**: `_process_atm_option_footprint()`
- **882**: `_process_all_strike_footprints()`
- **975**: `process_websocket_data()` main handler
- **1765**: `/api/options-footprint-data` endpoint

### Frontend (`templates/chart.html`)

- **2473-3100**: Complete Options Footprint code
- **2490**: `toggleOptFP()` — Footprint toggle
- **2515**: `ofpResample()` — Timeframe conversion
- **2541**: `ofpBuildLive()` — Format conversion
- **2568**: `ofpSetupFpCanvas()` — Canvas setup
- **2595**: `drawOfpFootprint()` — Render footprint
- **2705**: `initOptFPCharts()` — Initialize charts
- **2770**: `loadOfpHistory()` — Load data
- **2850**: `switchOfpStrike()` — Change strike
- **2875**: `populateStrikeDropdown()` — Create dropdown
- **2910**: `ofpHandleLiveTick()` — Real-time update

---

## API Reference

### Endpoint: `/api/options-footprint-data`

**Parameters**:
```
type: 'CE' | 'PE'
offset: '-300' | '-200' | '-100' | '0' | '100' | '200' | '300'
days: 1 (default, current day only)
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

**Example Call**:
```
GET /api/options-footprint-data?type=CE&offset=100&days=1
```

---

## Database

### File
```
footprint_data_OPTIONS_ATM.db
```

### All Symbols (14 Total)
```
NIFTY_CE_0      NIFTY_PE_0
NIFTY_CE_-100   NIFTY_PE_-100
NIFTY_CE_100    NIFTY_PE_100
NIFTY_CE_-200   NIFTY_PE_-200
NIFTY_CE_200    NIFTY_PE_200
NIFTY_CE_-300   NIFTY_PE_-300
NIFTY_CE_300    NIFTY_PE_300
```

### Typical Data Volume
- 1 day: ~1000 candles per symbol (1-minute)
- Per candle: ~150 price levels (footprint)
- Total: ~12.25 MB for all 14 symbols

---

## Implementation Status

✅ **Complete & Verified**

- [x] All 14 strikes subscribed
- [x] Real-time processing for all strikes
- [x] Database storage for all combinations
- [x] Socket.IO emission with offset filtering
- [x] Frontend chart display per offset
- [x] Dropdown persistence (no reset)
- [x] Strike switching works
- [x] Real-time updates properly filtered
- [x] Footprint visualization
- [x] Multi-timeframe support
- [x] Volume filters working

---

## Testing Checklist

- [ ] Open Options Footprint tab
- [ ] Verify dropdown shows 7 strike options
- [ ] Select different strike
- [ ] Check charts update with new data
- [ ] Verify dropdown value persists
- [ ] Toggle footprint ON/OFF
- [ ] Check volume filters apply
- [ ] Change timeframe (1/3/5/15m)
- [ ] Monitor real-time updates
- [ ] Check LTP updates in header
- [ ] Verify database has all 14 symbols

---

## Common Searches

| Looking For | Try This |
|-------------|----------|
| How strikes are stored | Search: "symbol format" |
| How offsets work | Search: "offset mapping" |
| Real-time processing | Search: "WebSocket tick" |
| Chart initialization | Search: "initOptFPCharts" |
| Data filtering | Search: "ofpCurrentOffset" |
| Footprint drawing | Search: "drawOfpFootprint" |
| API response format | Search: "Response:" in QUICK_REFERENCE |
| Database queries | Search: "Database Queries" |
| Error handling | Search: "Error Handling" |
| Performance metrics | Search: "Performance" |

---

## Version History

| Date | Commit | Changes |
|------|--------|---------|
| 2026-06-23 | 425ee30 | Multi-strike real-time updates, UI fixes, all 5 critical fixes |
| 2026-06-23 | — | Created complete documentation set |

---

## Support

For questions or issues:

1. Check **QUICK_REFERENCE.md** → "Common Issues"
2. Search documentation files for keywords
3. Review code in files referenced by line numbers
4. Check console logs in browser (F12)
5. Review database with SQL queries in documentation

---

## Summary

This documentation set provides:
- ✅ Complete system overview
- ✅ Detailed implementation reference
- ✅ Architecture and data flow diagrams
- ✅ Code snippets and examples
- ✅ API and database reference
- ✅ Troubleshooting guide
- ✅ Quick lookup reference

**Total Documentation**: 89 KB across 5 main files  
**Status**: Production ready  
**Last Updated**: June 23, 2026

---

## Document Recommendations

**For Managers**: BEHAVIOR_SUMMARY.md (High-level overview)  
**For Developers**: QUICK_REFERENCE.md + BEHAVIOR.md (Implementation details)  
**For Architects**: ARCHITECTURE.md (System design)  
**For QA/Testing**: BEHAVIOR_ANALYSIS_COMPLETE.md (Verification checklist)  
**For Maintenance**: QUICK_REFERENCE.md (Code locations)
