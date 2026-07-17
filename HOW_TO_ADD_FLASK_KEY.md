# How to Add Flask Secret Key to .env

## Current Status
Your `.env` file already has:
```
FLASK_SECRET_KEY=dev-secret-key-change-in-production
```

## For Development (Current Setup)
The current key is fine for local testing. No changes needed!

## For Production (Generate Secure Key)

### Step 1: Generate a Secure Key
Run this command:
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**Example output:**
```
AbCdEfGhIjKlMnOpQrStUvWxYz1234567890_-ABC
```

### Step 2: Copy the Generated Key
Copy the output (the long random string)

### Step 3: Update Your .env File

**Option A: Using Text Editor**
1. Open `.env` file in your text editor
2. Find line 3: `FLASK_SECRET_KEY=dev-secret-key-change-in-production`
3. Replace with: `FLASK_SECRET_KEY=your-generated-key-here`
4. Save the file

**Example after update:**
```
# Flask Configuration (Development)
FLASK_ENV=development
FLASK_SECRET_KEY=AbCdEfGhIjKlMnOpQrStUvWxYz1234567890_-ABC

# Upstox API Configuration
# Token valid until: 21 Mar 2027
UPSTOX_ANALYTICS_TOKEN=eyJ0eXAi...
```

**Option B: Using Command Line**
```bash
# Generate and save in one command
python3 << 'SCRIPT'
import secrets

key = secrets.token_urlsafe(32)
print(f"Generated key: {key}")

# Update .env file
with open('.env', 'r') as f:
    lines = f.readlines()

with open('.env', 'w') as f:
    for line in lines:
        if line.startswith('FLASK_SECRET_KEY='):
            f.write(f'FLASK_SECRET_KEY={key}\n')
        else:
            f.write(line)

print("✅ .env file updated with new Flask secret key")
SCRIPT
```

### Step 4: Verify the Update
```bash
grep FLASK_SECRET_KEY .env
```

Should show your new key

### Step 5: Restart the App
```bash
python3 footprint_web_app_upstox.py
```

---

## Current .env File Structure

Your `.env` file should look like this:

```ini
# Flask Configuration (Development)
FLASK_ENV=development
FLASK_SECRET_KEY=dev-secret-key-change-in-production

# Upstox API Configuration
# Token valid until: 21 Mar 2027
UPSTOX_ANALYTICS_TOKEN=eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ...

# CORS Configuration
CORS_ALLOWED_ORIGINS=http://localhost:5001,http://127.0.0.1:5001

# Session Cookie Security
SECURE_SESSION_COOKIE=false
```

---

## Important Notes

### For Development
- Current key is fine
- No need to change unless you want

### For Production
- **MUST generate a new secure key**
- Use: `python3 -c "import secrets; print(secrets.token_urlsafe(32))"`
- Never use same key across environments
- Store in secrets vault, not in .env file

### Key Requirements
- ✅ Should be random (use secrets module)
- ✅ Should be long (32+ characters)
- ✅ No spaces or special chars except `_` and `-`
- ✅ Keep it secret (don't commit to git)

---

## Quick Commands

**Generate new key:**
```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

**View current key:**
```bash
grep FLASK_SECRET_KEY .env
```

**Update key in .env:**
```bash
sed -i '' 's/^FLASK_SECRET_KEY=.*/FLASK_SECRET_KEY=YOUR_NEW_KEY_HERE/' .env
```

**Verify it's set:**
```bash
python3 -c "import os; from dotenv import load_dotenv; load_dotenv(); print(f'Key set: {bool(os.getenv(\"FLASK_SECRET_KEY\"))}')"
```

