from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import time
import os
import json
import pandas as pd
import re
from pprint import pprint
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
if not GITHUB_TOKEN:
    print(" WARNING: No GITHUB_TOKEN found in environment; unauthenticated requests may be rate-limited.")

HEADERS = {"Authorization": f"token {GITHUB_TOKEN}"} if GITHUB_TOKEN else {}
SESSION = requests.Session()
SESSION.headers.update(HEADERS)

OUT_ROOT = Path("data")
OUT_ROOT.mkdir(parents=True, exist_ok=True) 

OUT_DIFF_DIR = Path("data/diffsets")
OUT_DIFF_DIR.mkdir(parents=True, exist_ok=True)

# new structure roots
OUT_DIFFSETS = OUT_ROOT / "diffsets"
OUT_COMMITS = OUT_ROOT / "commits"
OUT_DIFFSETS.mkdir(parents=True, exist_ok=True)
OUT_COMMITS.mkdir(parents=True, exist_ok=True)


ACCESSIBILITY_KEYWORDS = [
    "accessibility", "a11y", "screenreader", "talkback", "voiceover", "semantics", "semanticslabel",
    "contrast", "colorblind", "focus", "aria", "label", "alt", "theme", "font", "fontsize", "text",
    "zoom", "scaling", "responsive", "ui", "ux", "layout", "widget", "component", "interface",
    "adaptive", "dark mode", "light mode", "animation", "navigation", "scroll", "swipe", "gesture",
    "tap", "touch", "drag", "focusable", "readability", "translation", "i18n", "rtl", "mirroring"
]

def check_keyword(k, msg_lower):
    if " " in k:
        pattern = re.escape(k.lower())
    else:
        pattern = r'\b' + re.escape(k.lower()) + r'\b'
    if re.search(pattern, msg_lower):
        return k
    return None

def find_keywords(msg_lower):
    matches = []

    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(check_keyword, k, msg_lower) for k in ACCESSIBILITY_KEYWORDS]
        for f in futures:
            result = f.result()
            if result:
                matches.append(result)
    print('matches', matches)
    return matches

def fetch_repo_metadata(owner: str, repo: str):


    repo_url = f"https://api.github.com/repos/{owner}/{repo}"
    headers_meta = {"Accept": "application/vnd.github.mercy-preview+json, application/vnd.github.v3+json"}
    headers_meta.update(HEADERS)

    meta = None
    try:
        r = SESSION.get(repo_url, headers=headers_meta, timeout=30)
    except Exception:
        r = None

    if _rate_handle(r):
        try:
            r = SESSION.get(repo_url, headers=headers_meta, timeout=30)
        except Exception:
            r = None

    if r and r.status_code == 200:
        try:
            meta = r.json()
        except Exception:
            meta = None

    description = ""
    topics = []
    languages_list = []

    if meta:
        description = meta.get("description") or ""
        topics = meta.get("topics") or []

        languages_url = meta.get("languages_url") or f"https://api.github.com/repos/{owner}/{repo}/languages"
        headers_lang = {"Accept": "application/vnd.github.v3+json"}
        headers_lang.update(HEADERS)
        try:
            rl = SESSION.get(languages_url, headers=headers_lang, timeout=30)
        except Exception:
            rl = None

        if _rate_handle(rl):
            try:
                rl = SESSION.get(languages_url, headers=headers_lang, timeout=30)
            except Exception:
                rl = None

        if rl and rl.status_code == 200:
            try:
                lang_map = rl.json()
                languages_list = list(lang_map.keys())
            except Exception:
                languages_list = []

    # TODO: review writing to file for columns in return
    return {"description": description, "topics": topics, "languages": languages_list}

def save_compare_diff(owner: str, repo:str, base_sha: str, head_sha: str):

    url = f"https://api.github.com/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}"
    headers = {"Accept": "application/vnd.github.v3.diff"}
    headers.update(HEADERS)

    for attempt in range(5): 
        r = None
        try:
            r = SESSION.get(url, headers=headers, timeout=30)
        except Exception as e:
            # transient network error
            if attempt < 4:
                time.sleep(1 + attempt * 2)
                continue
            return None

        if _rate_handle(r):
            continue

        if r.status_code == 200: 
            # stored under data/diffsets/<app_name>/<repo>_<head>_<base>.txt
            app_dir = OUT_DIFFSETS / repo
            app_dir.mkdir(parents=True, exist_ok=True)
            filename = f"{head_sha}_{base_sha}.txt"
            path = app_dir / filename
            try:
                path.write_text(r.text, encoding="utf-8")
                return path
            except Exception:
                return None
        elif r.status_code in (202, 409):
            time.sleep(1 + attempt * 2)
            continue
        else:
            return None

    return None


def save_commit_message(repo: str, commit_hash: str, message: str):
    try:
        # stored under data/commits/<app_name>/<head>.txt
        app_dir = OUT_COMMITS / repo
        app_dir.mkdir(parents=True, exist_ok=True)
        path = app_dir / f"{commit_hash}.txt"
        path.write_text(message or "", encoding="utf-8")
        return path
    except Exception:
        return None

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
    url = f"https://api.github.com/search/issues?q=is:issue+repo:{owner}/{repo}+state:closed"
    headers = {"Accept" : "application/vnd.github+json",
               "Authorization" : f"Bearer {GITHUB_TOKEN}"}
    print(f"CHECKING  {owner}/{repo}....")
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
            requests = json.loads(r.text)['items']

            for req_body in requests:
                print(req_body.keys())
                matches_title = find_keywords(req_body['title'].lower())
                matches_body = find_keywords(req_body['body'].lower())
                # matches_comments = find_keywords(req_body['comments'].lower())
                issue_num = req_body['url'].split('/')[-1]
                
                repo_url = req_body['repository_url']
                if matches_title or matches_body:
                    commits_url = f'https://api.github.com/repos/{owner}/{repo}/issues/{issue_num}/timeline'
                    print("==FOUND MATCHING ISSUE, EXTRACTING COMMITS==") 
                    try:
                        r = SESSION.get(commits_url, headers=headers, timeout=30)
                    except Exception as e:
                        # transient network error
                        if atmpt < 4:
                            time.sleep(1 + atmpt * 2)
                            continue
                        return None

                    if _rate_handle(r):
                        continue
                    
                    
                    metadata = {"description": "", "topics": [], "languages": []}
                    try:
                        metadata = fetch_repo_metadata(owner, repo) or metadata
                    except Exception:
                        metadata = metadata
                    
                    if r.status_code == 200: 
                        requests = json.loads(r.text)
                        for commit in requests:
                            print(commit["event"])
                            if commit["event"] == "commited":
                                print("Commit DATA")
                                pprint(commit)
                                diff_files = []
                                for parent in commit["parents"]:
                                    try:
                                        path = save_compare_diff(owner, repo, parent, commit.hash)
                                        if path:
                                            diff_files.append(str(path))
                                    except Exception as e:
                                        print(f"  WARN: failed to save diff for {parent}..{commit.hash}: {e}")
                                input()
                                r = {
                                    "repo": repo_url,
                                    "hash": commit["sha"],
                                    "author": commit["author"]["name"] if commit["author"] else "unknown",
                                    "email": commit["author"]["email"] if commit["author"] else "unknown",
                                    "date": commit["author"]["date"].strftime("%Y-%m-%d") if commit["author"] else "unknown",
                                    "message": commit["message"], 
                                    "parents": ", ".join(commit["parents"]) if commit["parents"] else "",
                                    "description": metadata.get("description", ""),
                                    "topics": ", ".join(metadata.get("topics", [])),
                                    "languages": ", ".join(metadata.get("languages", [])),
                                    "diff_files": ";".join(diff_files)
                                }
                                
                                try:
                                    save_commit_message(repo, commit.hash, commit["message"])
                                except Exception as e:
                                    print(f"  WARN: failed to save commit message for {commit["hash"]}: {e}")
                            elif commit["event"] == "closed" and commit["commit_url"]:
                                pass 
                            
                    
                    elif r.status_code in (202, 409):
                        time.sleep(1 + atmpt * 2)
                        continue
                    else:
                        return None
                    
        elif r.status_code in (202, 409):
            time.sleep(1 + atmpt * 2)
            continue
        else:
            return None


if __name__ == "__main__":
    data = pd.read_csv('apps.csv')
    for repo in data['repository']:
        owner, repoN = repo.replace("https://github.com/", "").split("/")
        get_repository_issues(owner, repoN)