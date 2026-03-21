#!/bin/bash
# Auto login/logout for Afaaqs Foot Print Server
# Usage: auto_session.sh login | logout

ACTION=$1
COOKIE_FILE="/opt/finalfootprint/.session_cookie"
BASE_URL="http://localhost:5002"

if [ "$ACTION" = "login" ]; then
    curl -s -c "$COOKIE_FILE" -X POST "$BASE_URL/login" \
        -H "Content-Type: application/json" \
        -d '{}' >> /var/log/footprint_session.log 2>&1
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-login triggered" >> /var/log/footprint_session.log

elif [ "$ACTION" = "logout" ]; then
    curl -s -b "$COOKIE_FILE" "$BASE_URL/logout" >> /var/log/footprint_session.log 2>&1
    rm -f "$COOKIE_FILE"
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Auto-logout triggered" >> /var/log/footprint_session.log

else
    echo "Usage: $0 login|logout"
    exit 1
fi
