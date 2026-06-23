# Re-Login Same Day — Options Footprint Chart Behavior

## Scenario
User logs out and logs back in during the same trading day.

**Example**: 
- First login: 09:30 AM (start trading)
- Some trading activity (data stored in database)
- User logs out: 11:00 AM
- **User logs back in: 11:45 AM (same day)**
- What happens to the chart?

---

## Complete Re-Login Flow

### Step 1: Logout (Previous Session)

```
User clicks "Logout"
    ↓
Session destroyed
    ↓
WebSocket disconnected (self.ws_client.disconnect())
    ↓
UpstoxAPI instance removed from authenticated_users
    ↓
Backend state cleared (candles, volumes, categories for all 14 strikes)
    ↓
Frontend session ends
    ↓
Database still intact (data persisted to footprint_data_OPTIONS_ATM.db)
```

**What's Preserved**:
- ✅ All candles stored in database (09:30-11:00)
- ✅ Footprint levels preserved
- ✅ ATM strike record in database

**What's Lost**:
- ❌ Backend in-memory state (ofp_strike_candles, ofp_strike_volumes, etc.)
- ❌ WebSocket connection
- ❌ Live candle being built
- ❌ Frontend session storage

---

### Step 2: Login Again (Same Day, 11:45 AM)

**What Happens**:

```
User clicks "Login"
    ↓
POST /login endpoint called
    ↓
New UpstoxAPI() instance created
    ├─ Fresh in-memory state initialized (empty)
    ├─ Backend state cleared (no old candles in memory)
    ├─ No connection to previous session
    └─ Clean slate for this session
    ↓
WebSocket connected (UpstoxWebSocketV3)
    ├─ Subscribe to NIFTY futures
    ├─ Subscribe to NIFTY spot (NSE_INDEX)
    ├─ Subscribe to India VIX
    └─ Start receiving live ticks
    ↓
subscribe_options_strikes() called
    ├─ Calculate ATM based on current NIFTY spot
    ├─ Recalculate 14 strike combinations
    ├─ Subscribe all 14 instruments
    └─ Start processing real-time data
    ↓
WebSocket ticks resume
    ├─ process_websocket_data() receives new ticks
    ├─ Builds NEW candles (from 11:45 AM onwards)
    ├─ Stores NEW candles to database
    └─ Emits Socket.IO events to frontend
```

---

## Frontend Behavior on Re-Login Same Day

### What User Sees

```
Before Logout (09:30-11:00):
  Charts show: ATM option prices with real-time candles
  Data in memory: Last few candles for current offset
  
After Logout:
  ✗ Charts disappear (session destroyed)
  ✗ Terminal disconnected
  
After Re-Login (11:45):
  Step 1: User clicks Options Footprint tab
  Step 2: initOptFPCharts() called
  Step 3: loadOfpHistory('CE') called
    ├─ API call: /api/options-footprint-data?type=CE&offset=0&days=1
    ├─ clear_old_session_data() runs
    │   └─ Would delete timestamp < today_00:00 (but all today's data preserved!)
    ├─ get_stored_data() retrieves
    │   └─ Returns candles from 09:30-11:00 (PLUS any new data from 11:45+)
    └─ Charts display with history
    
  Charts now show:
    ✓ Historical data: 09:30-11:00 (from database)
    ✓ New data: 11:45+ (real-time)
    ✓ Combined view of entire trading day so far
```

---

## Database State During Re-Login

### Before Logout (11:00 AM)

```
footprint_data_OPTIONS_ATM.db

NIFTY_CE_0:
  Candles stored: 09:30:00 → 11:00:00 (30 candles approx.)
  Footprint levels: Stored for all candles
  Last candle: Started at 10:59:00, closed at 11:00:00

NIFTY_PE_0, NIFTY_CE_±100, NIFTY_PE_±100, etc.:
  Similar for each of 14 symbols
  
Database Size: ~100 KB (current day data)
```

### During Logout

```
No database changes
Database state FROZEN at 11:00 AM
Data persisted and accessible
```

### After Re-Login (11:45 AM)

**Step 1: API Call with days=1**
```
GET /api/options-footprint-data?type=CE&offset=0&days=1

clear_old_session_data() runs:
  ├─ Calculates: today_00:00 = 2026-06-23 00:00:00 (midnight)
  ├─ Query: DELETE WHERE timestamp < today_00:00
  ├─ Result: NOTHING deleted (all data is from today!)
  └─ Database state unchanged

get_stored_data() filters:
  ├─ Query: SELECT * WHERE timestamp >= today_00:00
  ├─ Result: Returns ALL 09:30-11:00 data (today's data)
  └─ Frontend receives: ~30 candles from morning session
```

**Step 2: Live Ticks Resume**
```
New candles created: 11:45:00 onwards
Backend in-memory state: Fresh (empty)
Backend starts building new candles from scratch
Database: Stores BOTH old (09:30-11:00) AND new (11:45+)

Result:
  Historical data: 09:30-11:00 visible on chart
  Real-time data: 11:45+ updates live
  Gap: 11:00-11:45 (user was logged out, no data collected)
```

---

## Key Points

### ✅ What's Preserved
- All candles and footprint data from 09:30-11:00
- Database entries for all 14 strike combinations
- ATM strike information
- No data loss during logout

### ⚠️ Gap in Data Collection
- **11:00-11:45**: No data collected (user was logged out)
- Charts show gap (11:00-11:45 missing)
- This is expected behavior (no backend running during logout)

### ✅ Real-Time Resumes
- After re-login, WebSocket connects immediately
- Fresh candles created from 11:45 onwards
- New candles stored to database (mixed with old data)
- Charts update in real-time with new ticks

### ✅ ATM Lock Preserved
- ATM strike locked at first login (09:30)
- Remains locked throughout the day
- Used for all subsequent logins that day
- Doesn't recalculate on re-login

---

## Data Timeline Example

```
Timeline for Same Trading Day (2026-06-23):

09:30 AM → First Login
  ├─ WebSocket connects
  ├─ ATM locked at 24100
  ├─ Subscribe all 14 strikes
  └─ Start collecting data

09:30-11:00 AM → Trading Session 1
  ├─ ~30 candles generated per strike
  ├─ Data stored to database
  └─ Database size: ~100 KB

11:00 AM → User Logs Out
  ├─ WebSocket disconnected
  ├─ Backend session destroyed
  ├─ Database still has 09:30-11:00 data
  └─ No data collected during logout

11:00-11:45 AM → User Away (No Data)
  ├─ No WebSocket connection
  ├─ No candles created
  ├─ No ticks processed
  └─ Database unchanged

11:45 AM → Re-Login (Same Day)
  ├─ New UpstoxAPI instance created
  ├─ WebSocket connects (fresh)
  ├─ ATM re-fetched (likely same: 24100)
  ├─ Subscribe all 14 strikes again
  └─ Start collecting from 11:45

11:45 AM Onwards → Trading Session 2
  ├─ NEW candles created from 11:45 onwards
  ├─ Data appended to database
  ├─ Charts show 09:30-11:00 (history) + 11:45+ (live)
  └─ Database size growing

Example Data in Database:
  2026-06-23 09:30:00 → NIFTY_CE_0 candle 1 ✓
  2026-06-23 09:31:00 → NIFTY_CE_0 candle 2 ✓
  ... (28 more candles from session 1)
  2026-06-23 11:00:00 → NIFTY_CE_0 candle 30 ✓
  
  [GAP: 11:00-11:45, no data]
  
  2026-06-23 11:45:00 → NIFTY_CE_0 candle 1 (new session) ✓
  2026-06-23 11:46:00 → NIFTY_CE_0 candle 2 (new session) ✓
  ... (continues)
```

---

## Frontend Chart Display

### What User Sees After Re-Login

```
Charts (After clicking Options Footprint tab):

Time Axis:
  09:30────────11:00    11:45──────────
  ├─ Historical ─┤      ├─ Live Updates ─┤
  │              │      │                │
  ├──────────────┤  GAP  ├────────────────┤
  │ From DB      │      │ Real-time      │
  │ (30 candles) │      │ (building)     │
  └──────────────┘      └────────────────┘

Prices:
  Morning Session (09:30-11:00):
    ATM CE: 132.05 (open) → 134.25 (close)
    ATM PE: 115.65 (open) → 113.80 (close)
  
  Current Session (11:45+):
    ATM CE: 134.20 (current LTP)
    ATM PE: 113.85 (current LTP)
    Updating live every tick

Footprint:
  ✓ Visible for 09:30-11:00 (if toggle enabled)
  ✓ Visible for 11:45+ (real-time as ticks arrive)
  ✗ Not visible for 11:00-11:45 (gap period)
```

---

## Important Behavior Details

### ATM Lock Consistency

**Scenario 1: ATM doesn't change**
```
First login 09:30: ATM = 24100
Logout 11:00
Re-login 11:45: ATM = 24100 (still same)

Result:
  ✓ Charts show consistent data
  ✓ Same 14 strikes for entire day
  ✓ No confusion in data interpretation
```

**Scenario 2: NIFTY spot moved, but ATM stays locked**
```
First login 09:30: NIFTY = 24100, ATM locked = 24100
By 11:45: NIFTY = 24150 (moved 50 points)
Re-login 11:45: ATM locked = 24100 (unchanged!)

Result:
  ✓ Charts still use 24100 ATM
  ✓ Historical and real-time data consistent
  ✓ ATM lock prevents confusion
```

### Database Integrity

**After Re-Login Same Day**:
```
✓ All old data preserved (09:30-11:00)
✓ New data appended (11:45+)
✓ No data loss
✓ No data corruption
✓ No duplicate records (different timestamps)

Database Result:
  Single sorted timeline: 09:30 → 11:00 [GAP] 11:45 → ...
```

---

## Summary Table

| Aspect | Before Logout | During Logout | After Re-Login |
|--------|---------------|---------------|---|
| **WebSocket** | Connected | Disconnected | Connected (fresh) |
| **In-Memory State** | Active | N/A | Fresh (empty) |
| **Database** | Growing | Frozen | Growing again |
| **Charts** | Showing | Hidden | Show history + new |
| **ATM Lock** | Active (24100) | Persisted | Same (24100) |
| **Data Collection** | Active | Stopped | Active |
| **14 Strikes** | Subscribed | N/A | Re-subscribed |

---

## User Experience

### Seamless Continuation ✅

```
User Perspective:

1. Trade in morning (09:30-11:00)
   → Charts show real-time data

2. Logout at 11:00
   → Charts disappear
   → Data saved to database

3. Re-login at 11:45
   → Click Options Footprint tab
   → Charts load with morning data (history)
   → Real-time data resumes from 11:45
   → No data loss
   → Natural continuation of trading day
```

### Gap Period Visible ⚠️

```
Charts show:
  09:30-11:00: Smooth candle progression
  11:00-11:45: BLANK (gap, user was away)
  11:45+: Smooth candle progression (live)

This is expected and correct behavior
```

---

## Recommendations

### For Trading Continuity
1. **Morning Session**: Login and keep trading until break
2. **Logout**: Safe to logout; all data saved
3. **Afternoon Session**: Re-login; continue with full day's history
4. **Charts**: Show complete daily story (including gaps)

### For Data Analysis
1. Charts display entire trading day timeline
2. Gaps represent periods when user was logged out
3. No artificial data (only actual trading data)
4. All 14 strikes tracked throughout day

### If You Want to Avoid Gaps
1. Keep session active throughout trading day
2. Or accept gaps as natural logout periods
3. Consider monitoring data points before logout

---

## Conclusion

**When you re-login same day**:

✅ **Historical data preserved** (09:30-11:00 available)  
✅ **New data collected** (11:45+ starts accumulating)  
✅ **Charts show both** (history + real-time mixed)  
⚠️ **Gap appears** (11:00-11:45 missing, expected)  
✅ **No data loss** (everything saved to database)  
✅ **ATM lock consistent** (same strikes all day)  

Charts provide a **complete and honest view** of your trading day, including any logout periods. This is the desired behavior!

---

**Status**: ✅ Documented Behavior  
**Database**: All session data preserved  
**ATM Lock**: Consistent across re-login
