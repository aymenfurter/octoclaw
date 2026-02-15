---
name: gh-status-check
description: |
  Check the current operational status of all GitHub services.
  Queries the public githubstatus.com API -- no authentication required.
  Use when the user says: "is github down", "github status", "check github",
  "are github actions working", "github service status"
metadata:
  verb: check
---

# GitHub Status Check Skill

Query the GitHub Status API to report on current platform health.

The API is public and requires no authentication. Base URL: `https://www.githubstatus.com/api/v2/`

## Steps

### 1. Fetch Overall Status

```bash
curl -s https://www.githubstatus.com/api/v2/status.json
```

This returns a JSON object with `status.indicator` (one of `none`, `minor`, `major`, `critical`) and `status.description`.

### 2. Fetch Component Statuses

```bash
curl -s https://www.githubstatus.com/api/v2/components.json
```

Each component has a `name` and `status` field. Key components to report on:
- Git Operations
- API Requests
- Actions
- Packages
- Pages
- Codespaces
- Copilot
- Pull Requests
- Issues

Component status values: `operational`, `degraded_performance`, `partial_outage`, `major_outage`.

### 3. Check for Unresolved Incidents

```bash
curl -s https://www.githubstatus.com/api/v2/incidents/unresolved.json
```

If there are active incidents, extract:
- Incident name and status (`investigating`, `identified`, `monitoring`, `resolved`)
- Affected components
- Latest update message and timestamp

### 4. Present the Status Report

```markdown
## GitHub Status - <timestamp>

**Overall**: <indicator emoji> <description>

### Services
| Service | Status |
|---------|--------|
| Git Operations | operational |
| API Requests | operational |
| Actions | degraded_performance |
| ... | ... |

### Active Incidents (if any)
**<incident name>** -- <status>
- Impact: <affected components>
- Latest update (<timestamp>): <message>
```

Use these indicators:
- `operational` -> "OK"
- `degraded_performance` -> "Degraded"
- `partial_outage` -> "Partial Outage"
- `major_outage` -> "Major Outage"

### 5. Summary

Tell the user:
- Whether GitHub is fully operational or has issues
- Which specific services are affected (if any)
- Whether there are active incidents and their current status
