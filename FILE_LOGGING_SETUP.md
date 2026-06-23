# File-Based Logging System — 5-Day Retention

**Status**: ✅ **IMPLEMENTED**  
**Commit**: `fa2e12c`  
**Date**: June 23, 2026  
**Retention**: 5 days (automatic cleanup)

---

## Overview

Your application now has a comprehensive file-based logging system that:

✅ **Logs to files** in the `logs/` directory  
✅ **Creates daily log files** (format: `footprint_YYYYMMDD.log`)  
✅**Retains logs for 5 days** automatically  
✅ **Deletes old logs** after 5-day retention period  
✅ **Logs both to file and console** (console: INFO level, file: DEBUG level)  
✅ **Provides API endpoint** to view log statistics  
✅ **Automatic cleanup** on application startup  

---

## How It Works

### Log File Location

```
your-project-directory/
├── logs/
│   ├── footprint_20260623.log
│   ├── footprint_20260622.log
│   ├── footprint_20260621.log
│   ├── footprint_20260620.log
│   └── footprint_20260619.log  (after 5 days, this is deleted)
└── footprint_web_app_upstox.py
```

### Daily Log Rotation

- **New log file created** each day (UTC/Server time)
- **Format**: `footprint_YYYYMMDD.log`
- **Example**: 
  - June 23: `footprint_20260623.log`
  - June 24: `footprint_20260624.log`
  - June 25: `footprint_20260625.log`

### Automatic Cleanup

- **Runs on app startup** → Checks all log files
- **Compares file modification time** with current date
- **Deletes logs older than 5 days**
- **Example**:
  ```
  Day 1 (June 20): Create footprint_20260620.log
  Day 6 (June 25): footprint_20260620.log is 5+ days old → DELETED
  ```

---

## Log Levels

### What Gets Logged

| Level | Console | File | Use Case |
|-------|---------|------|----------|
| **DEBUG** | ❌ No | ✅ Yes | Detailed diagnostic info |
| **INFO** | ✅ Yes | ✅ Yes | General information |
| **WARNING** | ✅ Yes | ✅ Yes | Warning messages |
| **ERROR** | ✅ Yes | ✅ Yes | Error details |
| **CRITICAL** | ✅ Yes | ✅ Yes | Critical issues |

### Example Log Output

```
2026-06-23 09:15:30 - INFO     - footprint_app - 🚀 Footprint Application Started
2026-06-23 09:15:30 - INFO     - footprint_app - 🔄 Checking instrument data...
2026-06-23 09:15:32 - INFO     - footprint_app - ✅ Instrument data check complete
2026-06-23 09:15:33 - INFO     - footprint_app - 🌐 Starting Flask-SocketIO server
2026-06-23 09:15:33 - INFO     - footprint_app - 📍 Server running on http://0.0.0.0:5001
2026-06-23 09:15:45 - INFO     - footprint_app - 🔐 User login successful
2026-06-23 09:20:15 - INFO     - footprint_app - 🔒 Locked ATM footprint strike: 23600
2026-06-23 09:15:15 - WARNING  - footprint_app - ⏰ Pre-open detected (09:05), waiting for market open...
2026-06-23 17:30:00 - INFO     - footprint_app - 🚪 User logging out
```

---

## API Endpoints

### Get Log Statistics

**Endpoint**: `GET /api/logs-stats`

**Example Request**:
```bash
curl http://localhost:5001/api/logs-stats
```

**Example Response**:
```json
{
  "success": true,
  "data": {
    "log_count": 5,
    "total_size_mb": 12.45,
    "log_dir": "logs",
    "retention_days": 5,
    "logs": [
      {
        "name": "footprint_20260623.log",
        "size_mb": 2.85,
        "created": "2026-06-23 17:30:15"
      },
      {
        "name": "footprint_20260622.log",
        "size_mb": 3.12,
        "created": "2026-06-22 18:45:22"
      },
      {
        "name": "footprint_20260621.log",
        "size_mb": 2.56,
        "created": "2026-06-21 16:20:10"
      },
      {
        "name": "footprint_20260620.log",
        "size_mb": 2.34,
        "created": "2026-06-20 15:10:05"
      },
      {
        "name": "footprint_20260619.log",
        "size_mb": 1.58,
        "created": "2026-06-19 14:30:00"
      }
    ]
  }
}
```

---

## Files Created/Modified

### New Files

**File**: `log_manager.py` (164 lines)

Contains:
- `LogManager` class — Core logging management
- Log file creation and rotation
- Automatic cleanup logic
- API statistics methods
- Helper functions for easy logging

**Features**:
- Thread-safe logging
- Automatic directory creation
- Daily log file rotation
- Configurable retention period
- Log statistics and reporting

### Modified Files

**File**: `footprint_web_app_upstox.py`

Changes:
1. **Import statement** (Line 14):
   ```python
   from log_manager import initialize_logging, get_logger
   ```

2. **Logging initialization** (Lines 485-489):
   ```python
   # Initialize logging system with 5-day retention
   logger = initialize_logging(log_dir='logs', retention_days=5)
   logger.info("🚀 Footprint Application Started")
   ```

3. **Log statistics API** (Lines 2378-2385):
   ```python
   @app.route('/api/logs-stats')
   def get_logs_stats():
       # Returns log file statistics
   ```

4. **Shutdown logging** (Lines 2411-2419):
   ```python
   finally:
       logger.info("🛑 Server shutdown")
   ```

---

## Usage Examples

### 1. View Logs in Terminal

```bash
# Real-time log tail (last 10 lines, follow new)
tail -f logs/footprint_20260623.log

# View entire log file
cat logs/footprint_20260623.log

# Search for specific events
grep "ERROR" logs/footprint_20260623.log

# Count log messages by level
grep -c "ERROR" logs/footprint_20260623.log
```

### 2. Check Log Size

```bash
# Total logs size
du -sh logs/

# Individual file sizes
ls -lh logs/
```

### 3. Check Logs via Browser

```
http://localhost:5001/api/logs-stats
```

This shows:
- Total number of log files
- Total size in MB
- List of all logs with sizes and dates

### 4. Automatic Cleanup Verification

```bash
# Day 1-5: Logs present
ls -l logs/
# Output: Shows 5 recent log files

# Day 6 (after 5-day retention):
# App starts → Cleanup runs → Old logs deleted
ls -l logs/
# Output: Shows only newest logs (oldest deleted)
```

---

## Configuration

### Change Retention Period

Edit `footprint_web_app_upstox.py` line 486:

```python
# Current: 5 days
logger = initialize_logging(log_dir='logs', retention_days=5)

# Change to 7 days:
logger = initialize_logging(log_dir='logs', retention_days=7)

# Change to 3 days:
logger = initialize_logging(log_dir='logs', retention_days=3)
```

### Change Log Directory

```python
# Current: logs/
logger = initialize_logging(log_dir='logs', retention_days=5)

# Custom directory:
logger = initialize_logging(log_dir='application_logs', retention_days=5)
```

---

## Log Format

Each log entry follows this format:

```
{TIMESTAMP} - {LEVEL:8s} - {LOGGER_NAME} - {MESSAGE}
```

### Components

| Part | Example | Description |
|------|---------|-------------|
| **TIMESTAMP** | `2026-06-23 09:15:30` | Date and time in IST |
| **LEVEL** | `INFO    ` | Log level (8 chars, padded) |
| **LOGGER_NAME** | `footprint_app` | Application name |
| **MESSAGE** | `🚀 Footprint Application Started` | Log message with emoji |

### Example Lines

```
2026-06-23 09:15:30 - INFO     - footprint_app - 🚀 Footprint Application Started
2026-06-23 09:15:45 - INFO     - footprint_app - 🔐 User user_1 login successful
2026-06-23 09:20:10 - ERROR    - footprint_app - ❌ WebSocket connection failed: Connection refused
2026-06-23 17:30:00 - WARNING  - footprint_app - ⚠️ No data for CE, offset=0
```

---

## Console vs File Logging

### Console Output (Terminal)

- **Level**: INFO and above (less verbose)
- **Purpose**: Real-time visibility
- **Best for**: Quick monitoring
- **Contains**: Key events only

### File Output (logs/*.log)

- **Level**: DEBUG and above (all messages)
- **Purpose**: Detailed record keeping
- **Best for**: Troubleshooting and analysis
- **Contains**: Everything (very detailed)

---

## Cleanup Schedule

### Automatic Cleanup

- **Runs**: Every time app starts
- **Frequency**: On app restart/redeployment
- **Action**: Deletes files older than N days
- **Example**:
  ```
  App starts on Day 6
  → Checks all log files
  → Finds files from Day 1 (6 days old)
  → Deletes them (older than 5-day retention)
  → Keeps files from Day 2-6 (5 days recent)
  ```

### Manual Cleanup

```bash
# Delete all logs
rm -rf logs/

# Delete logs older than 5 days manually
find logs/ -name "*.log" -mtime +5 -delete
```

---

## Storage Considerations

### Disk Space

**Average daily log size**: ~2-3 MB  
**With 5-day retention**: ~12-15 MB total  
**With 7-day retention**: ~16-20 MB total

Example:
```
5-day retention:    12-15 MB
10-day retention:   24-30 MB
30-day retention:   60-90 MB
```

### Backup Recommendations

```bash
# Backup logs directory
tar -czf logs_backup_$(date +%Y%m%d).tar.gz logs/

# Restore from backup
tar -xzf logs_backup_20260623.tar.gz
```

---

## Troubleshooting

### Issue: Logs not being created

**Check**:
1. Verify `logs/` directory exists: `ls -la logs/`
2. Check directory permissions: `ls -ld logs/`
3. Check file permissions: `ls -la logs/*.log`

**Solution**:
```bash
# Create logs directory if missing
mkdir -p logs

# Fix permissions
chmod 755 logs
chmod 644 logs/*.log
```

### Issue: Old logs not being deleted

**Check**:
1. App was restarted
2. Check file modification times: `ls -la logs/`
3. Verify retention setting in code

**Solution**:
```bash
# Force cleanup manually
python -c "
from log_manager import LogManager
mgr = LogManager(retention_days=5)
mgr.cleanup_old_logs()
"
```

### Issue: Logs growing too large

**Check**:
1. Number of log files: `ls logs/ | wc -l`
2. Total size: `du -sh logs/`
3. Retention period too long

**Solution**:
- Reduce retention period (e.g., 3 days instead of 5)
- Increase log cleanup frequency
- Manually delete old logs

---

## Features

✅ **Automatic rotation** — New file each day  
✅ **5-day retention** — Configurable  
✅ **Auto-cleanup** — On app startup  
✅ **Dual output** — Console + File  
✅ **API endpoint** — View statistics  
✅ **Thread-safe** — Safe for multi-threaded app  
✅ **Structured format** — Easy to parse  
✅ **Timezone-aware** — Uses IST format  
✅ **Low overhead** — Efficient logging  
✅ **No external deps** — Uses only stdlib  

---

## Summary

| Aspect | Detail |
|--------|--------|
| **Files Created** | 1 (`log_manager.py`) |
| **Files Modified** | 1 (`footprint_web_app_upstox.py`) |
| **Log Directory** | `logs/` |
| **Log File Format** | `footprint_YYYYMMDD.log` |
| **Retention Period** | 5 days (configurable) |
| **Cleanup Trigger** | App startup |
| **Console Level** | INFO and above |
| **File Level** | DEBUG and above |
| **API Endpoint** | `GET /api/logs-stats` |
| **Thread-Safe** | Yes |
| **Disk Space (5 days)** | ~12-15 MB |

---

**Implementation**: ✅ Complete  
**Status**: Ready for production  
**Commit**: `fa2e12c`  
**Date**: June 23, 2026
