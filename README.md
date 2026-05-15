# Mobile Accessibility Commits

## GitHub API

```
curl -L \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  <URL>
```

### Endpoints of interest

**Get languages and lines by language:**
```
https://api.github.com/repos/OWNER/REPO/languages
```

**Search issues by repository name & state:**

(Other queries can be added to the URL.s see [ref](https://github.blog/changelog/2026-04-02-improved-search-for-github-issues-is-now-generally-available/))

```
curl -H 'Accept: application/vnd.github.text-match+json' \
    'https://api.github.com/search/issues?q=repo:{owner}/{repo}+state:closed'
```

example:
```
curl -H 'Accept: application/vnd.github.text-match+json' \
    'https://api.github.com/search/issues?q=repo:Automattic/simplenote-android+state:closed'
```

**Get issues:**
```
https://api.github.com/repos/OWNER/REPO/issues/NUM/timeline
```


**Get all repository info, find topics (tags):**
```
https://api.github.com/repos/OWNER/REPO | grep topics 
```

**Getting all issues or pull requests that are cross referenced with each other**
API documentation link
```
https://docs.github.com/en/graphql/reference/objects#crossreferencedevent
```


## Issue Extraction Endpoint

```sh
curl -H 'Accept: application/vnd.github.text-match+json' \
    'https://api.github.com/repos/Automattic/simplenote-android/issues/1808/timeline'
```

```sh
curl -H 'Accept: application/vnd.github.text-match+json' \
    'https://api.github.com/search/issues?q=repo:appditto/natrium_wallet_flutter+state:closed'
```