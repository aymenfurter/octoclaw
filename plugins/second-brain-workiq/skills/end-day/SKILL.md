---
name: end-day
description: |
  Wrap up the day by fetching meeting summaries from Microsoft 365 via WorkIQ
  and updating today's daily note with outcomes and reflections.
  Use when the user says: "end my day", "wrap up", "end of day", "daily review", "close the day"
metadata:
  verb: review
---

# End of Day Review Skill

Close out the day by fetching meeting summaries, reviewing task completion, and capturing reflections.

## Steps

### 1. Read Today's Daily Note

```bash
TODAY=$(date +%Y-%m-%d)
cat /data/notes/daily/${TODAY}.md 2>/dev/null || echo "No daily note found for today."
```

### 2. Fetch Meeting Summaries via WorkIQ

Pull meeting summaries and action items from today's meetings:

```bash
workiq ask -q "For each meeting I had today $(date +%Y-%m-%d), provide: 1) The meeting title, 2) A brief 2-3 sentence summary of what was discussed, 3) Any action items or follow-ups assigned to me, 4) Key decisions that were made. Format each meeting as a section with these details."
```

### 3. Fetch Communication Highlights

Pull any important emails or Teams messages from today:

```bash
workiq ask -q "Summarize the most important emails and Teams messages I received today $(date +%Y-%m-%d). Focus on: action items, decisions needed, and FYI items. Group by priority."
```

### 4. Review Task Completion

From today's daily note, categorize tasks:
- **Completed**: Lines with `- [x]`
- **Incomplete**: Lines with `- [ ]` (these will roll over tomorrow)
- Calculate completion percentage

### 5. Update Today's Daily Note

Append the following sections to today's daily note:

```markdown
## Meeting Summaries
### <Meeting 1 Title>
- **Summary**: <what was discussed>
- **Action Items**: <tasks assigned to me>
- **Decisions**: <key decisions>

### <Meeting 2 Title>
...

## Communication Highlights
- <important email/message summary>
...

## Day Review
- **Tasks completed**: X of Y (Z%)
- **Incomplete tasks**: (will roll over)
  - [ ] <task 1>
  - [ ] <task 2>

## Reflections
(space for user reflections -- prompt the user to add any thoughts)
```

### 6. Save Updated Note

Write the updated content back to `/data/notes/daily/${TODAY}.md`.

### 7. Summary

Tell the user:
- How many meetings were summarized
- Task completion rate for the day
- Number of action items captured
- Remind them about incomplete tasks that will roll over
