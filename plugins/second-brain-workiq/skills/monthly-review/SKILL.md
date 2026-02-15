---
name: monthly-review
description: |
  Generate a monthly retrospective by analyzing weekly reviews, long-term task progress,
  and deep Microsoft 365 productivity analytics via WorkIQ.
  Use when the user says: "monthly review", "month summary", "monthly retrospective", "summarize my month"
metadata:
  verb: review
---

# Monthly Review Skill

Create a comprehensive monthly retrospective from weekly reviews, daily notes, and deep M365 analytics.

## Steps

### 1. Determine the Review Period

```bash
# Current month boundaries
YEAR=$(date +%Y)
MONTH=$(date +%m)
MONTH_NAME=$(date +%B)
START_DATE="${YEAR}-${MONTH}-01"
END_DATE=$(date +%Y-%m-%d)
echo "Monthly review: ${MONTH_NAME} ${YEAR} (${START_DATE} to ${END_DATE})"
```

### 2. Read All Weekly Reviews for This Month

```bash
ls /data/notes/weekly/*-weekly.md 2>/dev/null | while read f; do
  FILE_DATE=$(basename "$f" | cut -d'-' -f1-3)
  echo "=== Weekly Review: ${FILE_DATE} ==="
  cat "$f"
  echo ""
done
```

### 3. Read All Daily Notes for the Month

```bash
YEAR=$(date +%Y)
MONTH=$(date +%m)
ls /data/notes/daily/${YEAR}-${MONTH}-*.md 2>/dev/null | while read f; do
  echo "=== $(basename $f .md) ==="
  cat "$f"
  echo ""
done
```

### 4. Consolidate Monthly Tasks

Across all daily notes for the month:
- Count total tasks created, completed, and abandoned
- Identify recurring themes in tasks
- Find tasks that persisted across multiple weeks (chronic open items)
- Track task velocity (tasks completed per week trend)

### 5. Fetch Deep Productivity Analytics via WorkIQ

```bash
workiq ask -q "Provide my detailed productivity analytics for $(date +%B) $(date +%Y): 1) Total meetings and hours, broken down by week, 2) Meeting-free time blocks (deep work hours), 3) Top 10 collaborators with interaction frequency, 4) Email volume trends (sent vs received per week), 5) Teams message activity, 6) Documents I created or edited, 7) My busiest and quietest days, 8) After-hours activity. Format as structured sections."
```

### 6. Fetch Goal and Project Progress via WorkIQ

```bash
workiq ask -q "Based on my activity this month ($(date +%B) $(date +%Y)), what topics and projects did I spend the most time on? Analyze my meetings, emails, Teams conversations, and document edits to identify my top 5 focus areas and estimate the relative time spent on each."
```

### 7. Read Topic Notes Updated This Month

```bash
find /data/notes/topics/ -name '*.md' -mtime -30 -exec basename {} .md \;
```

### 8. Compose the Monthly Review

Write to `/data/notes/monthly/<year>-<month>-monthly.md`:

```markdown
# Monthly Review: <Month Name> <Year>

## Month at a Glance
- **Days with notes**: X of Y workdays
- **Weekly reviews completed**: X
- **Total tasks created**: X
- **Total tasks completed**: X (Y%)
- **Total meetings**: X (Z hours)

## Key Accomplishments
- <major accomplishment from completed tasks and meetings>
- <accomplishment>
- <accomplishment>

## Focus Areas
| Area | Estimated Time | Trend |
|------|---------------|-------|
| <project/topic> | X hours | up/down/stable |
| <project/topic> | X hours | up/down/stable |

## Productivity Metrics
### Meetings
- **Total**: X meetings, Y hours
- **Weekly breakdown**: W1: Xh, W2: Xh, W3: Xh, W4: Xh
- **Deep work hours** (meeting-free blocks): X hours

### Communication
- **Emails**: X sent / Y received
- **Teams**: X messages
- **Top collaborators**: <name1>, <name2>, <name3>

### After Hours
- **After-hours activity**: X occurrences
- **Pattern**: <observation>

## Task Velocity
- **Week 1**: X created / Y completed
- **Week 2**: X created / Y completed
- **Week 3**: X created / Y completed
- **Week 4**: X created / Y completed
- **Trend**: improving / declining / stable

## Chronic Open Items
(Tasks open for 2+ weeks)
- [ ] <chronic task> -- open since <date>

## Topics and Knowledge Areas
- <topic 1> -- <what changed this month>
- <topic 2> -- <what changed this month>

## Reflections and Goals
### What went well
- (to be filled by user)

### What could improve
- (to be filled by user)

### Goals for next month
- (to be filled by user)
```

### 9. Save the Review

```bash
YEAR=$(date +%Y)
MONTH=$(date +%m)
mkdir -p /data/notes/monthly
```

Write to `/data/notes/monthly/${YEAR}-${MONTH}-monthly.md`.

### 10. Summary

Present the monthly highlights to the user, including:
- Productivity trend compared to available weekly data
- Top accomplishments
- Areas that need attention
- Chronic open items that should be addressed or dropped
