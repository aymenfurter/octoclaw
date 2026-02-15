---
name: wiki-summary
description: |
  Get a concise summary of a Wikipedia article on any topic.
  Use when the user says: "summarize from wikipedia", "what is <topic>",
  "tell me about <topic>", "wikipedia summary of", "quick facts about"
metadata:
  verb: summarize
---

# Wikipedia Summary Skill

Retrieve a concise summary of a Wikipedia article.

## Steps

### 1. Fetch the Summary

```bash
python3 -c "
import wikipedia
import json

try:
    page = wikipedia.page('TOPIC', auto_suggest=True)
    result = {
        'title': page.title,
        'summary': wikipedia.summary('TOPIC', sentences=5),
        'url': page.url,
        'categories': page.categories[:10],
        'references_count': len(page.references),
        'links_sample': page.links[:10]
    }
    print(json.dumps(result, indent=2))
except wikipedia.exceptions.DisambiguationError as e:
    print(json.dumps({'error': 'disambiguation', 'options': e.options[:10]}, indent=2))
except wikipedia.exceptions.PageError:
    print(json.dumps({'error': 'not_found'}, indent=2))
"
```

Replace `TOPIC` with the user's query.

### 2. Handle Disambiguation

If the result contains `"error": "disambiguation"`, present the options and ask the user to pick one:

```markdown
"<topic>" has multiple meanings on Wikipedia. Which one did you mean?
1. <option 1>
2. <option 2>
...
```

### 3. Handle Not Found

If the result contains `"error": "not_found"`, try a search instead:

```bash
python3 -c "
import wikipedia
import json
results = wikipedia.search('TOPIC', results=5)
print(json.dumps(results, indent=2))
"
```

### 4. Present the Summary

```markdown
## <Article Title>

<5-sentence summary>

**Source**: <Wikipedia URL>
**Categories**: <top categories>
**Related topics**: <sample links>
```

### 5. Summary

Deliver the summary to the user. Offer to do a deeper dive if they want the full article content, section breakdown, or related topics.
