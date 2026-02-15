---
name: daily-rollover
description: |
  Start a new day by rolling over unfinished tasks and preparing today's daily note.
  Pulls meeting schedule from Microsoft 365 via WorkIQ.
  Use when the user says: "start my day", "daily rollover", "new day", "morning setup"
metadata:
  verb: prepare
---

# Daily Rollover Skill

Create today's daily note, roll over unfinished tasks from yesterday, and pull in today's meeting schedule.

## Steps

### 1. Read Yesterday's Daily Note

```bash
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d)
cat /data/notes/daily/${YESTERDAY}.md 2>/dev/null || echo "No daily note found for ${YESTERDAY}."
```

### 2. Extract Unfinished Tasks from Yesterday

From yesterday's note, identify any tasks that are still incomplete:
- Lines starting with `- [ ]` are incomplete tasks
- Lines starting with `- [x]` are completed tasks (ignore these)
- Preserve any context or sub-items under each incomplete task

### 3. Fetch Today's Meeting Schedule via WorkIQ

Use the WorkIQ CLI to pull today's calendar from Microsoft 365:

```bash
workiq ask -q "List all my meetings and events scheduled for today $(date +%Y-%m-%d). For each meeting, include: the title, start time, end time, and list of attendees. Format as a bullet list."
```

### 4. Create Today's Daily Note

Write a new daily note at `/data/notes/daily/<today>.md`:

```markdown
# Daily Note - <today's date>

## Meetings Today
- <meeting 1 title> | <start>-<end> | <attendees>
- <meeting 2 title> | <start>-<end> | <attendees>
...

## Rolled Over Tasks
- [ ] <task from yesterday>
- [ ] <task from yesterday>

## Today's Tasks
- [ ] (space for new tasks)

## Notes
(empty section for the day's notes)
```

### 5. Save the Daily Note

```bash
TODAY=$(date +%Y-%m-%d)
mkdir -p /data/notes/daily
```

Write the formatted content to `/data/notes/daily/${TODAY}.md`.

### 6. Summary

Tell the user:
- How many tasks were rolled over
- How many meetings are on today's schedule
- Any meetings starting in the next 2 hours
