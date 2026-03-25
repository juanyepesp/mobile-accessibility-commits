from concurrent.futures import ThreadPoolExecutor, as_completed
from pydriller import Repository
import pandas as pd
from datetime import datetime, timedelta
import re
import os
import time
import requests
from urllib.parse import urlparse
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


def save_compare_diff(owner_repo: str, base_sha: str, head_sha: str):
    try:
        owner, repo = owner_repo.split("/")
    except Exception:
        return None

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

def save_commit_message(owner_repo: str, commit_hash: str, message: str):
    try:
        _, repo = owner_repo.split("/")
        # stored under data/commits/<app_name>/<head>.txt
        app_dir = OUT_COMMITS / repo
        app_dir.mkdir(parents=True, exist_ok=True)
        path = app_dir / f"{commit_hash}.txt"
        path.write_text(message or "", encoding="utf-8")
        return path
    except Exception:
        return None

def fetch_repo_metadata(owner_repo: str, app_name: str):
    try:
        owner, repo = owner_repo.split("/")
    except Exception:
        return {"description": "", "topics": [], "languages": []}

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


# Función para analizar un repositorio
def analyze_repo(repo_url):
    print(f" Analizando {repo_url}")
    results = []
    try:
        repo = Repository(
            repo_url,
            only_no_merge=True,
            #since=five_years_ago 
        )
        try:
            owner_repo = None
            s = repo_url.strip()
            if "/" in s and not s.startswith("http") and s.count("/") == 1:
                owner_repo = s
            else:
                parsed = urlparse(s)
                parts = parsed.path.strip("/").split("/")
                if len(parts) >= 2:
                    owner_repo = f"{parts[-2]}/{parts[-1].replace('.git','')}"
        except Exception:
            owner_repo = None

        # derive app_name for storage and fetch repo metadata (description, topics, languages)
        if owner_repo:
            app_name = owner_repo.split('/')[-1]
        else:
            try:
                parsed = urlparse(repo_url)
                parts = parsed.path.strip('/').split('/')
                app_name = parts[-1].replace('.git', '') if parts else repo_url.replace('/', '_')
            except Exception:
                app_name = repo_url.replace('/', '_')

        metadata = {"description": "", "topics": [], "languages": []}
        if owner_repo:
            try:
                metadata = fetch_repo_metadata(owner_repo, app_name) or metadata
            except Exception:
                metadata = metadata

        for commit in repo.traverse_commits():

            msg = commit.msg or ""
            msg_lower = msg.lower()

            # búsqueda de keywords con threads
            matches = find_keywords(msg_lower)
            if matches:
                diff_files = []
                for parent in commit.parents:
                    try:
                        if owner_repo:
                            path = save_compare_diff(owner_repo, parent, commit.hash)
                            if path:
                                diff_files.append(str(path))
                    except Exception as e:
                        print(f"  WARN: failed to save diff for {parent}..{commit.hash}: {e}")
                
                
                message = msg.strip()
                # save commit message under data/commits/<app_name>/<hash>.txt
                try:
                    cm_path = save_commit_message(owner_repo, commit.hash, message)
                except Exception:
                    cm_path = None
                
                results.append({
                    "repo": repo_url,
                    "hash": commit.hash,
                    "author": commit.author.name if commit.author else "unknown",
                    "email": commit.author.email if commit.author else "unknown",
                    "date": commit.author_date.strftime("%Y-%m-%d"),
                    # "message": msg.strip(),
                    "matches": ", ".join(matches), 
                    "parents": ", ".join(commit.parents) if commit.parents else "",
                    "diff_files": ";".join(diff_files),
                    "description": metadata.get("description", ""),
                    "topics": ", ".join(metadata.get("topics", [])),
                    "languages": ", ".join(metadata.get("languages", []))
                })    
                    

    except Exception as e:
        print(f" Error procesando {repo_url}: {e}")
    return results


# Función para buscar keywords (paralelizada)
def find_keywords(msg_lower):
    matches = []

    def check_keyword(k):
        if " " in k:
            pattern = re.escape(k.lower())
        else:
            pattern = r'\b' + re.escape(k.lower()) + r'\b'
        if re.search(pattern, msg_lower):
            return k
        return None

    # usa un ThreadPool para buscar las keywords en paralelo
    with ThreadPoolExecutor(max_workers=8) as executor:
        futures = [executor.submit(check_keyword, k) for k in ACCESSIBILITY_KEYWORDS]
        for f in futures:
            result = f.result()
            if result:
                matches.append(result)

    return matches


# Función principal para ejecutar en paralelo todos los repos
if __name__ == "__main__":
    with open("repos.txt") as f:
        repos = [r.strip() for r in f if r.strip()]

    all_results = []

    # pool principal para paralelizar repositorios
    with ThreadPoolExecutor(max_workers=5) as executor:
        future_to_repo = {executor.submit(analyze_repo, repo): repo for repo in repos}
        for future in as_completed(future_to_repo):
            repo = future_to_repo[future]
            try:
                results = future.result()
                all_results.extend(results)
                print(f" Completado: {repo} ({len(results)} commits relevantes)")
            except Exception as e:
                print(f" Fallo en {repo}: {e}")

    # Guardar resultados
    df = pd.DataFrame(all_results)
    output_path = "data/commits_accessibility_parallel.csv"
    df.to_csv(output_path, index=False)

    print(f"\n Total commits encontrados: {len(df)}")
    print(f" Archivo guardado en: {output_path}")