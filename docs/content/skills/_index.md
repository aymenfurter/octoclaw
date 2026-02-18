---
title: "Skills"
weight: 60
---

Skills are instructions that teach Octoclaw how to perform specific tasks. Each skill is a directory containing a `SKILL.md` file with YAML frontmatter and Markdown instructions.

## How Skills Work

When a user invokes a skill (by verb or topic match), the skill's instructions are loaded into the agent's context. The LLM uses these instructions to guide its behavior for that interaction.

Skills are not code -- they are natural language instructions that leverage the agent's existing tool capabilities (MCP servers, built-in tools, etc.).

## Skill Format

```
my-skill/
  SKILL.md           # Required
  (supporting files)  # Optional
```

### SKILL.md Structure

```markdown
---
name: My Skill
description: A brief description of what this skill does
metadata:
  verb: myverb
---

# My Skill

Detailed instructions for the agent on how to perform this skill.

## Steps

1. Do this first
2. Then do this
3. Finally do this

## Notes

- Important considerations
- Edge cases to handle
```

### Frontmatter Fields

| Field | Required | Description |
|---|---|---|
| `name` | Yes | Display name |
| `description` | Yes | Short description shown in listings |
| `metadata.verb` | Yes | Trigger word for the skill (e.g., `search`, `note`, `brief`) |

## Skill Sources

Skills come from four sources, tracked via a `.origin` file in each skill directory:

| Source | Location | Description |
|---|---|---|
| **Built-in** | `skills/` (project root) | Shipped with Octoclaw |
| **Agent-created** | `~/.octoclaw/skills/` | Created by the agent during conversations |
| **Plugin-provided** | `~/.octoclaw/skills/` | Installed when a plugin is enabled |
| **Marketplace** | `~/.octoclaw/skills/` | Downloaded from remote catalogs |

## Sections

- [Creating Skills](/skills/creating-skills/) -- How to write custom skills
- [Marketplace](/skills/marketplace/) -- Remote skill catalogs
- [Built-in Skills](/skills/builtin/) -- Documentation for included skills
