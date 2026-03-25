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

**Get issues:**
```
https://api.github.com/repos/OWNER/REPO/issues
```

**Get issues:**
```
https://api.github.com/repos/OWNER/REPO/issues/NUM/timeline
```


**Get all repository info, find topics (tags):**
```
https://api.github.com/repos/OWNER/REPO | grep topics 
```

