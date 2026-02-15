---
name: gh-incidents
description: |
  List recent and active GitHub incidents from githubstatus.com.
  Shows incident history, root causes, and resolution timelines.
  Use when the user says: "github incidents", "github outage history",
  "what happened on github", "recent github issues", "github downtime"
metadata:
  verb: list
---

# GitHub Incidents Skill

Retrieve recent and active incidents from the GitHub Status API.

## Steps

### 1. Fetch Unresolved Incidents

```bash
curl -s https://www.githubstatus.com/api/v2/incidents/unresolved.json
```

For each unresolved incident, extract:
- `name` -- incident title
- `status` -- `investigating`, `identified`, `monitoring`, `resolved`
- `impact` -- `none`, `minor`, `major`, `critical`
- `incident_updates` -- array of status updates with `body` and `updated_at`
- `components` -- affected services

### 2. Fetch Recent Resolved Incidents

```bash
curl -s https://www.githubstatus.com/api/v2/incidents.json
```

This returns the 50 most recent incidents. Filter to the last 7 days for relevance.

For each recent incident, extract:
- `name`
- `impact`
- `created_at` and `resolved_at` (to calculate duration)
- `components` affected
- Final update message

### 3. Present Active Incidents (if any)

```markdown
## Active GitHub Incidents

### <incident name>
- **Status**: <investigating/identified/monitoring>
- **Impact**: <minor/major/critical>
- **Affected**: <component list>
- **Started**: <created_at>
- **Duration so far**: <calculated>

**Timeline**:
- <timestamp>: <update body>
- <timestamp>: <update body>
```

### 4. Present Recent Incident History

```markdown
## Recent Incidents (last 7 days)

| Date | Incident | Impact | Duration | Services |
|------|----------|--------|----------|----------|
| <date> | <name> | minor | 23 min | Actions |
| <date> | <name> | major | 2h 15m | API, Git | 
```

If no incidents in the last 7 days, report that GitHub has been stable.

### 5. Summary

Tell the user:
- Number of active incidents (if any) and their severity
- How many incidents in the past 7 days
- Which services have been most affected recently
- Overall reliability assessment for the week
