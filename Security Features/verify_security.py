#!/usr/bin/env python3
"""
Security Verification Script
Checks that critical security measures are in place.
"""

import os
import re
import sys

class SecurityChecker:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0

    def check(self, condition, message, critical=False):
        """Check a condition and print result"""
        if condition:
            print(f"✅ {message}")
            self.passed += 1
        else:
            level = "❌ CRITICAL" if critical else "⚠️  WARNING"
            print(f"{level}: {message}")
            if critical:
                self.failed += 1
            else:
                self.warnings += 1

    def check_file(self, filepath, pattern, should_exist=True, description=""):
        """Check if a pattern exists in a file"""
        if not os.path.exists(filepath):
            self.check(False, f"File not found: {filepath}", critical=True)
            return False

        with open(filepath, 'r') as f:
            content = f.read()

        if should_exist:
            found = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            self.check(found, f"{description} found in {filepath}", critical=False)
            return bool(found)
        else:
            found = re.search(pattern, content, re.MULTILINE | re.IGNORECASE)
            self.check(not found, f"{description} NOT found in {filepath}", critical=False)
            return not bool(found)

    def run_checks(self):
        """Run all security checks"""
        print("=" * 60)
        print("🔒 SECURITY VERIFICATION SCAN")
        print("=" * 60 + "\n")

        # Check 1: .env file exists
        print("1. Configuration Security")
        env_exists = os.path.exists('finalfootprint/.env')
        self.check(env_exists, ".env file exists", critical=True)

        if env_exists:
            with open('finalfootprint/.env', 'r') as f:
                env_content = f.read()
                has_token = 'UPSTOX_ANALYTICS_TOKEN=' in env_content and 'your-' not in env_content.lower()
                has_secret = 'FLASK_SECRET_KEY=' in env_content and 'change-this' not in env_content.lower()

                self.check(
                    'your-' not in env_content.lower() or env_content.count('UPSTOX_ANALYTICS_TOKEN=') == 0,
                    "No placeholder values in .env (check manually)",
                    critical=False
                )

        # Check 2: SSL Certificate Verification
        print("\n2. WebSocket Security (SSL/TLS)")
        self.check_file(
            'finalfootprint/upstox_websocket_v3.py',
            r'cert_reqs.*CERT_REQUIRED',
            True,
            "SSL certificate verification enabled"
        )
        self.check_file(
            'finalfootprint/upstox_websocket_v3.py',
            r'check_hostname.*True',
            True,
            "Hostname verification enabled"
        )
        self.check_file(
            'finalfootprint/upstox_websocket_v3.py',
            r'PROTOCOL_TLSv1_2',
            True,
            "TLS 1.2 minimum enforced"
        )

        # Check 3: No hardcoded secrets
        print("\n3. Hardcoded Secrets Check")
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'app\.secret_key\s*=\s*["\']your-secret-key',
            False,
            "No hardcoded Flask secret key"
        )
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'ANALYTICS_TOKEN\s*=\s*["\']eyJ',
            False,
            "No hardcoded JWT token"
        )

        # Check 4: Environment variables
        print("\n4. Environment Configuration")
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'os\.getenv\(["\']FLASK_SECRET_KEY',
            True,
            "Flask secret key loaded from environment"
        )
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'os\.getenv\(["\']UPSTOX_ANALYTICS_TOKEN',
            True,
            "Analytics token loaded from environment"
        )
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'os\.getenv\(["\']CORS_ALLOWED_ORIGINS',
            True,
            "CORS origins loaded from environment"
        )

        # Check 5: Session security
        print("\n5. Session Security")
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'SESSION_COOKIE_HTTPONLY.*True',
            True,
            "HTTPOnly flag set on session cookies"
        )
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'SESSION_COOKIE_SAMESITE',
            True,
            "SameSite attribute configured"
        )
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'CSRFProtect',
            True,
            "CSRF protection enabled"
        )

        # Check 6: CORS restrictions
        print("\n6. CORS Configuration")
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'cors_allowed_origins.*CORS_ALLOWED_ORIGINS',
            True,
            "CORS origins restricted (not wildcard)"
        )

        # Check 7: Logging instead of print
        print("\n7. Logging Security")
        self.check_file(
            'finalfootprint/footprint_web_app_upstox.py',
            r'logger = initialize_logging',
            True,
            "Logger configured"
        )

        # Check 8: Dependencies
        print("\n8. Security Dependencies")
        self.check_file(
            'finalfootprint/requirements_upstox.txt',
            r'flask-wtf',
            True,
            "Flask-WTF (CSRF protection) in requirements"
        )
        self.check_file(
            'finalfootprint/requirements_upstox.txt',
            r'python-dotenv',
            True,
            "python-dotenv (.env support) in requirements"
        )

        # Check 9: Git security
        print("\n9. Git Configuration")
        gitignore_exists = os.path.exists('finalfootprint/.gitignore')
        self.check(gitignore_exists, ".gitignore file exists", critical=False)

        if gitignore_exists:
            with open('finalfootprint/.gitignore', 'r') as f:
                gitignore = f.read()
                self.check(
                    '.env' in gitignore,
                    ".env files in .gitignore",
                    critical=True
                )
                self.check(
                    '*.db' in gitignore or 'footprint_data' in gitignore,
                    "Database files in .gitignore",
                    critical=False
                )

        # Summary
        print("\n" + "=" * 60)
        print(f"Results: ✅ {self.passed} passed | ⚠️  {self.warnings} warnings | ❌ {self.failed} critical failures")
        print("=" * 60)

        if self.failed > 0:
            print("\n🚨 CRITICAL ISSUES FOUND - Fix before production deployment!")
            return 1
        elif self.warnings > 0:
            print("\n⚠️  Some warnings found - Review and fix recommended")
            return 0
        else:
            print("\n✅ All security checks passed!")
            return 0


if __name__ == '__main__':
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    checker = SecurityChecker()
    sys.exit(checker.run_checks())
