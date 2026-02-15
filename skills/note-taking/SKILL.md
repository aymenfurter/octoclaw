---
name: note-taking
description: 'Create, read, update, and organize personal notes. Use when the user asks to take a note, jot something down, save information for later, or manage their notes.'
metadata:
  verb: note
---

# Note Taking Skill

Manage the user's notes as plain text/markdown files in the data directory.

## Storage

All notes are stored as plain `.md` files in the home (data) directory at `~/notes/`.
Do NOT use a database, JSON blob, or any other structured format -- just simple files on disk.
This makes notes portable, grep-able, and easy to back up.

## Directory Structure

```
~/notes/
  quick.md            # Scratch pad for quick one-liners
  ideas.md            # Ideas and brainstorming
  meetings/
    2026-02-09.md     # Meeting notes by date
  projects/
    <project-name>.md # Per-project notes
  topics/
    <topic>.md        # Notes organized by topic
```

Create subdirectories as needed. Default to the top-level `~/notes/` for simple notes.

## Creating a Note

1. Determine the appropriate file based on context:
   - Quick thought or no category specified: append to `~/notes/quick.md`
   - Meeting notes: `~/notes/meetings/<date>.md`
   - Project-specific: `~/notes/projects/<project>.md`
   - Topic-specific: `~/notes/topics/<topic>.md`

2. Ensure the directory exists:
   ```bash
   mkdir -p ~/notes/meetings ~/notes/projects ~/notes/topics
   ```

3. Append the note with a timestamp header:
   ```bash
   echo -e "\n## $(date '+%Y-%m-%d %H:%M')\n\n<content>" >> ~/notes/<file>.md
   ```

## Reading Notes

- Show a specific note file:
  ```bash
  cat ~/notes/<file>.md
  ```

- List all notes:
  ```bash
  find ~/notes -name '*.md' -type f | sort
  ```

- Search across all notes:
  ```bash
  grep -rl "<search term>" ~/notes/
  ```

## Updating Notes

- To edit an existing note, read the file, modify the content, and write it back.
- When appending, always add a new timestamped section rather than overwriting.

## Deleting Notes

- Only delete when the user explicitly asks:
  ```bash
  rm ~/notes/<file>.md
  ```

## Tips

- Always confirm with the user before deleting or overwriting notes.
- When the user says "note that..." or "remember that...", save it to `quick.md` unless a better category is obvious.
- Keep note content concise but complete -- capture the user's intent faithfully.
- Use markdown formatting (headers, lists, bold) to keep notes scannable.
