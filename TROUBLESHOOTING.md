# Troubleshooting Guide

## Issue: "Connection error: Unexpected token '<', '<!doctype '... is not valid JSON"

This error occurs when the API returns HTML instead of JSON, usually due to authentication or API issues.

### Quick Diagnostic Steps

**Step 1: Verify your token is valid**
```bash
python3 diagnose_token.py
```

**Expected output:**
```
✅ SUCCESS! Token is valid and working!
```

**Step 2: Check the application logs**
Start the app and look for detailed error messages:
```bash
python3 footprint_web_app_upstox.py
```

Watch for messages like:
- `✅ Token verification successful` — Good!
- `❌ Token verification failed` — Token issue
- `❌ API Error 401` — Token expired
- `❌ Response is not JSON` — Server returning HTML

### Common Solutions

#### Solution 1: Token is Expired or Invalid
If you see `❌ Token expired or invalid`:

1. Go to: https://account.upstox.com/developer/apps#analytics
2. Click "Generate Token" in the Analytics section
3. Copy the new token
4. Update `.env` file:
   ```
   UPSTOX_ANALYTICS_TOKEN=<your-new-token>
   ```
5. Restart the application

#### Solution 2: Network/Firewall Issue
If the diagnostic script shows timeout or connection refused:

1. Check your internet connection
2. Try from a different network
3. Check if your firewall is blocking Upstox APIs
4. Try connecting directly: `curl https://api.upstox.com/v3/feed/market-data-feed/authorize -H "Authorization: Bearer YOUR_TOKEN"`

#### Solution 3: Wrong Token Format
If the diagnostic script fails to parse the token:

1. Ensure the token is copied completely (no extra spaces)
2. Check that it starts with `eyJ` (base64 JWT format)
3. The token must be a single line with no newlines

#### Solution 4: Environment Variable Not Loaded
If `.env` file exists but token is not being read:

1. Verify `.env` file exists:
   ```bash
   ls -la .env
   ```

2. Check file contents:
   ```bash
   grep UPSTOX_ANALYTICS_TOKEN .env
   ```

3. Verify it's not in `.gitignore` (it should be):
   ```bash
   grep "\.env" .gitignore
   ```

4. Try exporting manually:
   ```bash
   export UPSTOX_ANALYTICS_TOKEN=$(grep UPSTOX_ANALYTICS_TOKEN .env | cut -d'=' -f2)
   python3 footprint_web_app_upstox.py
   ```

### Detailed Troubleshooting

#### Check Application Logs

The app now provides detailed error messages. Look for:

**Good Login:**
```
🔑 Verifying analytics token with Upstox API...
🔑 Auth response: 200
✅ Token verification successful
📡 Started Upstox WebSocket V3
```

**Token Expired (401):**
```
🔑 Verifying analytics token with Upstox API...
🔑 Auth response: 401
❌ Token verification failed with status 401
```

**Invalid Response:**
```
🔑 Auth response: 200
❌ Failed to parse response: Expecting value: line 1 column 1 (char 0)
❌ Response text: <!doctype html>...
```

#### Run Diagnostic Tool

The `diagnose_token.py` script provides detailed information:

```bash
python3 diagnose_token.py
```

This will tell you:
- ✅ Token is valid
- ❌ Token is expired/invalid (401)
- ⚠️ API server error (5xx)
- ❌ Network connection issue
- ❌ Malformed token

### Manual API Test

Test the API directly with your token:

```bash
# Set your token
TOKEN="your-token-here"

# Test the endpoint
curl -v https://api.upstox.com/v3/feed/market-data-feed/authorize \
  -H "Authorization: Bearer $TOKEN" \
  -H "Accept: application/json"
```

**Expected response:**
```json
{
  "status": "success",
  "data": {
    "authorizedRedirectUri": "wss://wsfeeder-api.upstox.com/...",
    "authorized_redirect_uri": "wss://wsfeeder-api.upstox.com/..."
  }
}
```

### If Nothing Works

1. **Check Upstox Status**
   - Visit: https://status.upstox.com
   - Check if APIs are experiencing outages

2. **Clear Everything and Start Fresh**
   ```bash
   # Stop the app (Ctrl+C)
   
   # Remove any cached data
   rm -f *.db footprint_web_app_upstox.pyc
   rm -rf logs/ __pycache__/
   
   # Reinstall dependencies
   pip install -r requirements_upstox.txt --force-reinstall
   
   # Start fresh
   python3 footprint_web_app_upstox.py
   ```

3. **Contact Upstox Support**
   - If the diagnostic tool shows token is valid but API still fails
   - Go to: https://support.upstox.com
   - Provide the curl response showing the exact error

### Getting Help

**Questions to answer when asking for help:**

1. What does `python3 diagnose_token.py` output?
2. What error message do you see in the application logs?
3. Did the token recently expire? Check: https://account.upstox.com/developer/apps#analytics
4. Can you access https://api.upstox.com directly?
5. What's your network setup (home/office/VPN)?

### Key Files

- **App Logs:** `logs/footprint_*.log` (5-day retention)
- **Diagnostic Tool:** `diagnose_token.py`
- **Configuration:** `.env` (protected by .gitignore)
- **Token Source:** `https://account.upstox.com/developer/apps#analytics`

---

**Last Updated:** 12 July 2026  
**Token Expiry:** 21 March 2027 ⏰ Mark your calendar!
