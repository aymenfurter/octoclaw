---
name: weekly-review
description: |
  Generate a weekly summary by consolidating daily notes, reviewing task completion,
  and pulling Microsoft 365 productivity analytics via WorkIQ.
  Use when the user says: "weekly review", "week summary", "summarize my week", "weekly recap"
metadata:
  verb: review
---

# Weekly Review Skill

Produce a comprehensive weekly summary from daily notes, tasks, and Microsoft 365 analytics.

## Steps

### 1. Determine the Review Period

Calculate the date range for the past 7 days:

```bash
END_DATE=$(date +%Y-%m-%d)
START_DATE=$(date -v-7d +%Y-%m-%d 2>/dev/null || date -d "7 days ago" +%Y-%m-%d)
echo "Review period: ${START_DATE} to ${END_DATE}"
```

### 2. Read All Daily Notes for the Period

```bash
for i in $(seq 0 6); do
  DAY=$(date -v-${i}d +%Y-%m-%d 2>/dev/null || date -d "${i} days ago" +%Y-%m-%d)
  if [ -f /data/notes/daily/${DAY}.md ]; then
    echo "=== ${DAY} ==="
    cat /data/notes/daily/${DAY}.md
    echo ""
  fi
done
```

### 3. Consolidate Tasks Across the Week

From all daily notes:
- Collect all tasks that were **completed** (`- [x]`)
- Collect all tasks that are **still open** (`- [ ]`)
- Identify tasks that appeared multiple days (stuck/recurring)
- Count total tasks created vs completed

### 4. Fetch Weekly Meeting Analytics via WorkIQ

```bash
workiq ask -q "Provide my meeting analytics for the past 7 days (from $(date -v-7d +%Y-%m-%d 2>/dev/null || date -d '7 days ago' +%Y-%m-%d) to $(date +%Y-%m-%d)): 1) Total number of meetings, 2) Total hours in meetings, 3) Meetings I organized vs attended, 4) Recurring vs one-off meetings, 5) Which days were heaviest/lightest. Format as structured data."
```

### 5. Fetch Collaboration Analytics via WorkIQ

```bash
workiq ask -q "Who were the top 5 people I collaborated with most this past week (from $(date -v-7d +%Y-%m-%d 2>/dev/null || date -d '7 days ago' +%Y-%m-%d) to $(date +%Y-%m-%d))? Include meetings, emails, and Teams interactions. Also tell me how many emails I sent vs received, and how many Teams messages I sent."
```

### 6. Read Topic Notes for Changes

```bash
find /data/notes/topics/ -name '*.md' -mtime -7 -exec basename {} .md \;
```

### 7. Compose the Weekly Review

Write the review to `/data/notes/weekly/<end-date>-weekly.md`:

```markdown
# Weekly Review: <start-date> to <end-date>

## Week at a Glance
- **Days with notes**: X of 7
- **Tasks created**: X
- **Tasks completed**: X (Y%)
- **Meetings attended**: X (Z hours)

## Key Accomplishments
- <accomplishment derived from completed tasks and meeting outcomes>
- <accomplishment>

## Meeting Summary
- **Total meetings**: X
- **Total hours**: Y
- **Busiest day**: <day>
- **Lightest day**: <day>

## Collaboration
- **Top collaborators**: <names with interaction counts>
- **Emails**: X sent / Y received
- **Teams messages**: X sent

## Open Items
- [ ] <task still incomplete>
- [ ] <task still incomplete>

## Stuck Items
(Tasks that appeared in 3+ daily notes without completion)
- [ ] <stuck task>

## Topics Updated This Week
- <topic 1>
- <topic 2>

## Focus Areas for Next Week
- <suggestion based on open items and patterns>
```

### 8. Save the Review

```bash
END_DATE=$(date +%Y-%m-%d)
mkdir -p /data/notes/weekly
```

Write to `/data/notes/weekly/${END_DATE}-weekly.md`.

### 9. Summary

Present the review highlights to the user in a concise format.
