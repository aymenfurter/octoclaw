---
name: daily-briefing
description: 'Generate a daily briefing summarizing recent memory and relevant information. Use when the user asks for a morning briefing or daily summary.'
metadata:
  verb: brief
---

# Daily Briefing Skill

Compile a comprehensive daily briefing from memory.

## Steps

1. Read today's daily log (if it exists):
   ```bash
   cat ~/.octoclaw/memory/daily/$(date +%Y-%m-%d).md 2>/dev/null || echo "No entries yet today."
   ```

2. Read yesterday's daily log for continuity:
   ```bash
   cat ~/.octoclaw/memory/daily/$(date -v-1d +%Y-%m-%d).md 2>/dev/null || echo "No entries yesterday."
   ```

3. Scan topic notes for any recently updated items:
   ```bash
   find ~/.octoclaw/memory/topics/ -name '*.md' -mtime -2 -exec basename {} .md \;
   ```

4. Compile the briefing:
   - **Good morning** greeting
   - **Yesterday recap** -- key events from yesterday's log
   - **Pending items** -- anything left unfinished
   - **Active topics** -- recently updated topic notes
   - **Suggested actions** -- things the user might want to follow up on

## Format

Use emoji headers and keep it scannable:
```
Good morning! Here's your briefing for <date>:

**Yesterday**
- ...

**Active Topics**
- ...

**Suggested Actions**
- ...
```
