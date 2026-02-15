---
name: wiki-deep-dive
description: |
  Retrieve the full content of a Wikipedia article, broken down by sections,
  with references and images.
  Use when the user says: "full wikipedia article on", "deep dive into",
  "everything wikipedia knows about", "read me the wikipedia page for"
metadata:
  verb: explore
---

# Wikipedia Deep Dive Skill

Fetch the full content of a Wikipedia article and present it in a structured way.

## Steps

### 1. Fetch the Full Page

```bash
python3 -c "
import wikipedia
import json

try:
    page = wikipedia.page('TOPIC', auto_suggest=True)
    # Split content into sections by heading pattern
    import re
    sections = re.split(r'\n(== .+ ==)\n', page.content)

    result = {
        'title': page.title,
        'url': page.url,
        'sections': [],
        'images': page.images[:5],
        'references_count': len(page.references),
        'links_count': len(page.links)
    }

    # Parse sections
    current_heading = 'Introduction'
    current_body = ''
    for part in sections:
        if re.match(r'^== .+ ==$', part.strip()):
            if current_body.strip():
                result['sections'].append({'heading': current_heading, 'length': len(current_body.strip())})
            current_heading = part.strip().strip('= ')
            current_body = ''
        else:
            current_body += part

    if current_body.strip():
        result['sections'].append({'heading': current_heading, 'length': len(current_body.strip())})

    print(json.dumps(result, indent=2))
except wikipedia.exceptions.DisambiguationError as e:
    print(json.dumps({'error': 'disambiguation', 'options': e.options[:10]}, indent=2))
except wikipedia.exceptions.PageError:
    print(json.dumps({'error': 'not_found'}, indent=2))
"
```

### 2. Fetch Section Content on Demand

For longer articles, first present the table of contents and then fetch specific sections when the user asks:

```bash
python3 -c "
import wikipedia
import re

page = wikipedia.page('TOPIC', auto_suggest=True)
sections = re.split(r'\n(== .+ ==)\n', page.content)

# Find the requested section
target = 'SECTION_NAME'
current_heading = 'Introduction'
for part in sections:
    if re.match(r'^== .+ ==$', part.strip()):
        current_heading = part.strip().strip('= ')
    elif current_heading.lower() == target.lower():
        print(part.strip()[:3000])
        break
"
```

### 3. Present the Article Structure

```markdown
## <Article Title>

**URL**: <url>
**Sections**: X | **References**: Y | **Links**: Z

### Table of Contents
1. Introduction (<length> chars)
2. <Section Name> (<length> chars)
3. <Section Name> (<length> chars)
...

### Introduction
<first section content, truncated to reasonable length>
```

### 4. Interactive Follow-up

After presenting the overview, offer the user options:
- "Read section <name>" -- fetch and display a specific section
- "List references" -- show source URLs
- "Related topics" -- show linked Wikipedia articles
- "Save to notes" -- if the Second Brain plugin is enabled, save key points to `/data/notes/topics/<topic>.md`

### 5. Summary

Tell the user the article size, number of sections, and highlight the most substantial sections. Offer to read any section in detail.
