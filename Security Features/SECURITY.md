# Security Implementation Guide

## Critical Security Fixes Implemented

This document outlines the security improvements made to the Footprint application.

### 1. Secret Key Management ✅

**Issue:** Hard-coded Flask secret key exposed session forgery attacks.

**Fix:**
- Secret key now loaded from `FLASK_SECRET_KEY` environment variable
- If not set, generates random key on startup (ephemeral, lost on restart)
- **Action Required:** Set `FLASK_SECRET_KEY` in `.env` file for production

```bash
# Generate a secure key:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 2. API Token Protection ✅

**Issue:** Upstox JWT token was hard-coded in source code, exposing market data access.

**Fix:**
- Token now loaded from `UPSTOX_ANALYTICS_TOKEN` environment variable
- Never logged or printed (uses secure logger)
- **Action Required:** Set `UPSTOX_ANALYTICS_TOKEN` in `.env` file

**CRITICAL:** Never commit `.env` file to git!

### 3. SSL/TLS Certificate Verification ✅

**Issue:** WebSocket connections disabled SSL certificate verification, allowing MITM attacks.

**Fix:**
- Enabled `ssl.CERT_REQUIRED` validation
- Set `check_hostname=True`
- Minimum TLS version: 1.2

**Before:**
```python
self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})  # ❌ UNSAFE
```

**After:**
```python
sslopt = {
    "cert_reqs": ssl.CERT_REQUIRED,
    "check_hostname": True,
    "ssl_version": ssl.PROTOCOL_TLSv1_2
}
self.ws.run_forever(sslopt=sslopt)  # ✅ SECURE
```

### 4. CORS Restrictions ✅

**Issue:** `cors_allowed_origins="*"` allowed any domain to access your APIs.

**Fix:**
- CORS restricted to specific origins via `CORS_ALLOWED_ORIGINS` env variable
- **Action Required:** Set allowed domains in `.env`

**Before:**
```python
socketio = SocketIO(app, cors_allowed_origins="*")  # ❌ UNSAFE
```

**After:**
```python
cors_origins = os.getenv('CORS_ALLOWED_ORIGINS', 'http://localhost:5001')
socketio = SocketIO(app, cors_allowed_origins=cors_origins.split(','))  # ✅ SECURE
```

### 5. Session Security Hardening ✅

**Issue:** Session cookies vulnerable to XSS and CSRF attacks.

**Fix:**
- Added `SESSION_COOKIE_HTTPONLY = True` (prevents XSS access)
- Added `SESSION_COOKIE_SECURE = True` (HTTPS only in production)
- Added `SESSION_COOKIE_SAMESITE = Lax` (CSRF protection)
- Enabled CSRF protection with Flask-WTF

```python
app.config['SESSION_COOKIE_SECURE'] = True      # HTTPS only
app.config['SESSION_COOKIE_HTTPONLY'] = True    # No JS access
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'   # CSRF protection
app.config['WTF_CSRF_ENABLED'] = True           # Enable CSRF tokens
```

### 6. Logging Security ✅

**Issue:** Sensitive information printed to stdout (visible in logs).

**Fix:**
- Replaced all `print()` statements with proper logger calls
- Logger configured to exclude sensitive token data
- Sensitive debug information no longer visible in logs

### 7. Input Validation ✅

**Issue:** API endpoints accepted unvalidated user input, risking injection attacks.

**Fix:**
- Added `validate_symbol()` function - whitelist allowed characters
- Added `validate_timeframe()` function - whitelist valid values
- Added `validate_days()` function - bound integer ranges
- Applied validation to key API endpoints

### 8. CSRF Protection ✅

**Issue:** Forms vulnerable to Cross-Site Request Forgery attacks.

**Fix:**
- Integrated Flask-WTF CSRF protection
- CSRF tokens required for all POST/PUT/DELETE requests
- **Note:** HTML forms need to include `{{ csrf_token() }}` hidden field

### 9. Environment Configuration ✅

**Issue:** Hard-coded configuration for all environments (dev/staging/prod).

**Fix:**
- Created `.env.example` template
- Application loads configuration from `.env` file
- Different configs per environment supported

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements_upstox.txt
```

### 2. Configure Environment

```bash
# Copy the example to .env
cp .env.example .env

# Edit .env with your values:
# - FLASK_SECRET_KEY: Generate with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# - UPSTOX_ANALYTICS_TOKEN: Get from Upstox API console
# - CORS_ALLOWED_ORIGINS: Set your domain(s)
# - SECURE_SESSION_COOKIE: Set to 'true' for production with HTTPS
```

### 3. Protect .env File

Add to `.gitignore`:
```
.env
.env.local
.env.*.local
```

**Never commit the `.env` file!**

### 4. Run Application

```bash
python footprint_web_app_upstox.py
```

Or with gunicorn (production):

```bash
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:5001 \
  --env FLASK_ENV=production \
  --env FLASK_SECRET_KEY="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  --env UPSTOX_ANALYTICS_TOKEN="your-token-here" \
  footprint_web_app_upstox:app
```

## Production Deployment Checklist

- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_SECRET_KEY` to a strong random value
- [ ] Set `UPSTOX_ANALYTICS_TOKEN` in secrets manager (not .env)
- [ ] Set `CORS_ALLOWED_ORIGINS` to your actual domain(s)
- [ ] Set `SECURE_SESSION_COOKIE=true` (requires HTTPS)
- [ ] Use HTTPS/TLS for all connections
- [ ] Set proper `SESSION_COOKIE_SAMESITE` (Lax or Strict)
- [ ] Configure firewall rules
- [ ] Enable logging and monitoring
- [ ] Regular security updates for dependencies
- [ ] Rotate `UPSTOX_ANALYTICS_TOKEN` periodically

## Remaining Items to Address

See the main security analysis for additional items that should be addressed:

1. **Database Connection Management** - Use context managers for DB operations
2. **Rate Limiting** - Add API rate limiting middleware
3. **Input Validation** - Expand validation to all endpoints
4. **Authentication** - Implement proper multi-user authentication
5. **Monitoring** - Set up security monitoring and alerting
6. **SQLite in Production** - Consider migrating to PostgreSQL/MySQL

## Security Best Practices

1. **Never hardcode secrets** - Use environment variables or secrets vaults
2. **Validate all inputs** - Whitelist acceptable values
3. **Use HTTPS in production** - Redirect HTTP to HTTPS
4. **Keep dependencies updated** - Regular security patches
5. **Log security events** - Monitor for suspicious activity
6. **Use strong cryptography** - HTTPS, HMAC, proper hashing
7. **Implement proper authentication** - User verification
8. **Restrict access** - Principle of least privilege
9. **Monitor and audit** - Track all access and changes
10. **Prepare incident response** - Have a security incident plan

## Questions?

Refer to OWASP guidelines for additional security best practices:
https://owasp.org/www-project-web-security-testing-guide/
