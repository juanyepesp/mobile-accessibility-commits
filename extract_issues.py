import requests
import time
import os
import json

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print(" WARNING: No GITHUB_TOKEN found in environment; unauthenticated requests may be rate-limited.")

BASE_URL = "https://api.github.com/repos"

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)


# TODO: Rate limiting

def _rate_handle(resp):
    # simple rate-limit/backoff handling using GitHub headers
    if resp is None:
        return False
    if resp.status_code == 403:
        reset = resp.headers.get("X-RateLimit-Reset")
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining == "0" and reset:
            wait = int(reset) - int(time.time()) + 2
            if wait > 0:
                print(f" Rate limit hit, sleeping {wait}s")
                time.sleep(wait)
                return True
    return False

def get_repository_issues(owner, repo):
    url = f"{BASE_URL}/{owner}/{repo}/issues"
    headers = {"Accept" : "application/vnd.github+json"}

    for atmpt in range(5):
        r = None
        
        try:
            r = SESSION.get(url, headers=headers, timeout=30)
        except Exception as e:
            # transient network error
            if atmpt < 4:
                time.sleep(1 + atmpt * 2)
                continue
            return None

        if _rate_handle(r):
            continue

        if r.status_code == 200: 
            req_body = json.loads(r.text)[0]
            print(req_body['title'], req_body['url'], req_body['state'], req_body['body'], req_body['comments'])
        elif r.status_code in (202, 409):
            time.sleep(1 + atmpt * 2)
            continue
        else:
            return None


if __name__ == "__main__":
    get_repository_issues("Dimillian", "IceCubesApp")