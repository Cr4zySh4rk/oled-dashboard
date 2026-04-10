#!/usr/bin/env python3
"""
Pi-hole API diagnostic script.
Run this on the Pi to check if the Pi-hole API is reachable and auth works.

Usage:
    python3 test_pihole.py
    python3 test_pihole.py yourpassword
    python3 test_pihole.py yourpassword http://localhost
"""

import sys
import json

PASSWORD = sys.argv[1] if len(sys.argv) > 1 else ""
BASE_URL  = (sys.argv[2] if len(sys.argv) > 2 else "http://localhost").rstrip("/")

print(f"\n=== Pi-hole API Diagnostic ===")
print(f"Base URL : {BASE_URL}")
print(f"Password : {'(set)' if PASSWORD else '(empty — unauthenticated mode)'}")
print()

# ── 1. Check requests is installed ─────────────────────────────────────────
try:
    import requests
    print("[OK] requests library is installed")
except ImportError:
    print("[FAIL] requests is NOT installed!")
    print("       Fix: python3 -m pip install requests")
    sys.exit(1)

# ── 2. Check Pi-hole API is reachable ──────────────────────────────────────
try:
    r = requests.get(f"{BASE_URL}/api/version", timeout=3)
    print(f"[OK] API reachable — /api/version returned HTTP {r.status_code}")
    if r.status_code == 200:
        print(f"     {r.json()}")
except Exception as e:
    print(f"[FAIL] Cannot reach Pi-hole API at {BASE_URL}")
    print(f"       Error: {e}")
    print("       Check: is lighttpd running? (sudo systemctl status lighttpd)")
    sys.exit(1)

# ── 3. Auth (if password provided) ─────────────────────────────────────────
session = None
if PASSWORD:
    try:
        r = requests.post(f"{BASE_URL}/api/auth",
                          json={"password": PASSWORD}, timeout=3)
        print(f"\n[INFO] POST /api/auth → HTTP {r.status_code}")
        body = r.json()
        if r.status_code == 200 and "session" in body:
            sid  = body["session"]["sid"]
            csrf = body["session"]["csrf"]
            session = {"sid": sid, "csrf": csrf}
            print(f"[OK] Session created  sid={sid[:12]}...  csrf={csrf[:12]}...")
        elif r.status_code == 401:
            print("[FAIL] Wrong password — Pi-hole rejected it (HTTP 401)")
            print("       Use the App Password from: Pi-hole Settings → Web Interface")
            sys.exit(1)
        else:
            print(f"[WARN] Unexpected response: {body}")
    except Exception as e:
        print(f"[FAIL] Auth request failed: {e}")
        sys.exit(1)
else:
    print("\n[INFO] No password given — trying unauthenticated request")

# ── 4. Fetch summary stats ──────────────────────────────────────────────────
try:
    kwargs = {"json": session, "timeout": 5} if session else {"timeout": 5}
    r = requests.get(f"{BASE_URL}/api/stats/summary", **kwargs)
    print(f"\n[INFO] GET /api/stats/summary → HTTP {r.status_code}")

    if r.status_code == 200:
        body = r.json()
        q = body.get("queries", {})
        c = body.get("clients", {})
        print("[OK] Got stats successfully!")
        print(f"     Total queries   : {q.get('total', 'N/A')}")
        print(f"     Blocked         : {q.get('blocked', 'N/A')}")
        print(f"     % Blocked       : {round(q.get('percent_blocked', 0), 1)}%")
        print(f"     Unique domains  : {q.get('unique_domains', 'N/A')}")
        print(f"     Clients (total) : {c.get('total', 'N/A') if isinstance(c, dict) else c}")
    elif r.status_code == 401:
        print("[FAIL] Unauthenticated request was rejected (HTTP 401).")
        print("       Pi-hole requires a password. Run:")
        print("       python3 test_pihole.py YOUR_PASSWORD")
    else:
        print(f"[FAIL] Unexpected HTTP {r.status_code}")
        print(f"       Body: {r.text[:300]}")
except Exception as e:
    print(f"[FAIL] Summary request failed: {e}")
    sys.exit(1)

# ── 5. Blocking status ──────────────────────────────────────────────────────
try:
    kwargs = {"json": session, "timeout": 3} if session else {"timeout": 3}
    r = requests.get(f"{BASE_URL}/api/dns/blocking", **kwargs)
    print(f"\n[INFO] GET /api/dns/blocking → HTTP {r.status_code}")
    if r.status_code == 200:
        status = r.json().get("blocking", "unknown")
        print(f"[OK] Blocking status: {status}")
except Exception as e:
    print(f"[WARN] Blocking status check failed (non-fatal): {e}")

print("\n=== Diagnostic complete ===")
print("If all checks passed, the oled-dashboard should show Pi-hole stats.")
print("Make sure the widget's 'Password' field matches what you entered above.")
