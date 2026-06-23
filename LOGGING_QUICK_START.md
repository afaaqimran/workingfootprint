# File Logging — Quick Start Guide

**Status**: ✅ **READY TO USE**  
**Implementation**: Complete and deployed  
**Commit**: `c47bce6`

---

## What's New

Your application now has **automatic file-based logging** with:

- ✅ Daily log files in `logs/` directory
- ✅ Automatic 5-day retention
- ✅ Auto-delete logs older than 5 days
- ✅ Console + File logging
- ✅ API endpoint to check logs
- ✅ Zero configuration needed

---

## How to Use

### 1. Start the App Normally

```bash
python footprint_web_app_upstox.py
```

**That's it!** Logs are now being saved automatically.

---

### 2. View Logs in Terminal

```bash
# Watch logs in real-time
tail -f logs/footprint_20260623.log

# View entire log
cat logs/footprint_20260623.log

# Search for errors
grep "ERROR" logs/footprint_20260623.log

# See all log files
ls -lh logs/
```

---

### 3. Check Logs via Browser

**API Endpoint**:
```
http://localhost:5001/api/logs-stats
```

**Returns**:
```json
{
  "success": true,
  "data": {
    "log_count": 5,
    "total_size_mb": 12.45,
    "logs": [
      {"name": "footprint_20260623.log", "size_mb": 2.85, "created": "2026-06-23 17:30:15"},
      {"name": "footprint_20260622.log", "size_mb": 3.12, "created": "2026-06-22 18:45:22"},
      ...
    ]
  }
}
```

---

## Log File Details

### Location
```
your-project/logs/footprint_YYYYMMDD.log
```

### Example Files
```
logs/
├── footprint_20260623.log  (Today)
├── footprint_20260622.log  (Yesterday)
├── footprint_20260621.log  (2 days ago)
├── footprint_20260620.log  (3 days ago)
└── footprint_20260619.log  (4 days ago)
```

### File Size
- **Daily size**: ~2-3 MB
- **5-day total**: ~12-15 MB

---

## What Gets Logged

### Examples

```
✅ Application startup/shutdown
✅ User login/logout
✅ WebSocket connections
✅ Data processing events
✅ Errors and warnings
✅ Pre-open period detection
✅ ATM strike locking
✅ Options subscription
✅ Real-time data arrival
✅ API requests
```

### Example Log Output

```
2026-06-23 09:15:30 - INFO     - 🚀 Footprint Application Started
2026-06-23 09:15:45 - INFO     - 🔐 User login successful
2026-06-23 09:20:10 - ERROR    - ❌ WebSocket connection failed
2026-06-23 09:15:15 - WARNING  - ⏰ Pre-open detected, waiting...
```

---

## Automatic Cleanup

### How It Works

1. **App starts** → Logs initialization
2. **Cleanup runs** → Checks all log files
3. **Files older than 5 days** → **DELETED**
4. **Logs 1-5 days old** → **KEPT**

### Example

```
Day 1 (Jun 20): Created footprint_20260620.log
Day 6 (Jun 25): 
  - App starts
  - Cleanup detects footprint_20260620.log is 6 days old
  - FILE DELETED ✓
  - Keeps: footprint_20260625.log through footprint_20260621.log
```

---

## Configuration (Optional)

### Change Retention Period

Edit `footprint_web_app_upstox.py` line 487:

```python
# Current: 5 days
logger = initialize_logging(log_dir='logs', retention_days=5)

# To change to 7 days:
logger = initialize_logging(log_dir='logs', retention_days=7)
```

### Change Log Directory

```python
# Current: logs/
logger = initialize_logging(log_dir='logs', retention_days=5)

# To use custom directory:
logger = initialize_logging(log_dir='my_logs', retention_days=5)
```

---

## Common Tasks

### View Today's Logs
```bash
tail -f logs/footprint_$(date +%Y%m%d).log
```

### Find All Errors
```bash
grep "ERROR" logs/footprint_*.log
```

### Total Log Size
```bash
du -sh logs/
```

### List All Logs with Details
```bash
ls -lh logs/
```

### Delete All Logs Manually
```bash
rm -rf logs/
```

---

## Log Levels

| Level | Console | File | When |
|-------|---------|------|------|
| DEBUG | No | Yes | Detailed diagnostics |
| INFO | Yes | Yes | Important events |
| WARNING | Yes | Yes | Potential issues |
| ERROR | Yes | Yes | Errors that occurred |
| CRITICAL | Yes | Yes | Critical failures |

---

## Troubleshooting

### Logs not appearing?

1. Check if `logs/` directory exists:
   ```bash
   ls -la logs/
   ```

2. Check permissions:
   ```bash
   ls -ld logs/
   chmod 755 logs
   ```

3. Restart the app:
   ```bash
   python footprint_web_app_upstox.py
   ```

### Logs disappearing?

- Logs older than 5 days are automatically deleted
- This is expected behavior (auto-cleanup)
- To keep more history, increase retention period

---

## Files Added

1. **`log_manager.py`** (164 lines)
   - Core logging system
   - Automatic cleanup
   - Log management

2. **`FILE_LOGGING_SETUP.md`** (Detailed documentation)
   - Full configuration guide
   - API reference
   - Troubleshooting guide

---

## Summary

| Feature | Status |
|---------|--------|
| File logging | ✅ Active |
| Daily log files | ✅ Automatic |
| 5-day retention | ✅ Automatic |
| Auto-cleanup | ✅ On startup |
| API endpoint | ✅ `/api/logs-stats` |
| Console logging | ✅ INFO level |
| File logging | ✅ DEBUG level |
| Configuration | ✅ Easy to change |

---

**Implementation Date**: June 23, 2026  
**Status**: Production Ready  
**No Action Required**: System runs automatically

Start your app and logs will be saved automatically! 🎉
