---
name: foundry-agent-chat
description: |
  Create an ad-hoc Microsoft Foundry agent for a specific purpose using the new v2 Responses API.
  Build a custom prompt agent with optional tools, run a conversation, and clean up.
  Use when the user says: "create a foundry agent", "make an agent for", "foundry agent",
  "build an ai agent", "create an assistant", "spin up an agent", "agent for this task"
metadata:
  verb: create
---

# Foundry Agent Chat

Create an ad-hoc Foundry prompt agent tailored to a specific purpose using the new v2 Responses API with conversations.

## Prerequisites

The user must have completed the Foundry setup (the `setup-foundry` skill). They need:
- `FOUNDRY_PROJECT_ENDPOINT` -- the project endpoint URL
- `FOUNDRY_MODEL_DEPLOYMENT_NAME` -- the model deployment name

If these are not set, ask the user for the values.

## Steps

### 1. Define the Agent Purpose

Ask the user:
- What should the agent do? (e.g., "Write marketing copy", "Answer questions about our docs", "Translate text")
- Should it have any special instructions or persona?
- Does it need any tools? (code interpreter, file search, web search)

### 2. Create and Run the Agent

Use the following Python script. Customize the `agent_name`, `instructions`, and `tools` based on the user's requirements.

**Basic prompt agent (no tools):**

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")
model = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "<MODEL>")

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    openai_client = project_client.get_openai_client()

    # Create a purpose-built agent
    agent = project_client.agents.create_version(
        agent_name="AGENT_NAME_HERE",
        definition=PromptAgentDefinition(
            model=model,
            instructions="INSTRUCTIONS_HERE",
        ),
        description="DESCRIPTION_HERE",
    )
    print(f"Agent created: {agent.name} v{agent.version}")

    # Create a conversation
    conversation = openai_client.conversations.create()

    # Send the user's message
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="USER_MESSAGE_HERE",
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
    )

    # Print the response
    print(response.output_text)

    # Clean up
    project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    print("Agent cleaned up.")
PYEOF
```

**Agent with tools (code interpreter + web search):**

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import (
    PromptAgentDefinition,
    CodeInterpreterTool,
    CodeInterpreterToolAuto,
)

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")
model = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "<MODEL>")

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    openai_client = project_client.get_openai_client()

    # Create agent with tools
    agent = project_client.agents.create_version(
        agent_name="AGENT_NAME_HERE",
        definition=PromptAgentDefinition(
            model=model,
            instructions="INSTRUCTIONS_HERE",
            tools=[
                CodeInterpreterTool(container=CodeInterpreterToolAuto()),
                {"type": "web_search_preview"},
            ],
        ),
        description="DESCRIPTION_HERE",
    )
    print(f"Agent created: {agent.name} v{agent.version}")

    # Create a conversation
    conversation = openai_client.conversations.create()

    # Send the user's message
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="USER_MESSAGE_HERE",
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
    )

    # Print the response
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "output_text":
                    print(content.text)

    # Clean up
    project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    print("Agent cleaned up.")
PYEOF
```

### 3. Multi-turn Conversation

If the user wants to continue the conversation, reuse the same conversation ID without creating a new one:

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    openai_client = project_client.get_openai_client()

    # Reuse existing conversation and agent
    conversation_id = "CONVERSATION_ID_HERE"
    agent_name = "AGENT_NAME_HERE"

    response = openai_client.responses.create(
        conversation=conversation_id,
        input="FOLLOW_UP_MESSAGE_HERE",
        extra_body={"agent": {"name": agent_name, "type": "agent_reference"}},
    )

    print(response.output_text)
PYEOF
```

### 4. Present Results

- Show the agent's response to the user
- If the agent used tools (code interpreter, web search), summarize what it did
- For multi-turn conversations, keep track of the conversation ID and agent name

### 5. Clean Up

When the user is done, delete the agent version:

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    project_client.agents.delete_version(agent_name="AGENT_NAME", agent_version="VERSION")
    print("Agent cleaned up.")
PYEOF
```

## Agent Types Summary

| Use Case | Tools | Example |
|----------|-------|---------|
| Q&A / Chat | None | Customer support bot, writing assistant |
| Data Analysis | Code Interpreter | CSV analysis, chart generation, math solver |
| Research | Web Search | Market research, fact checking |
| Full-featured | Code Interpreter + Web Search | Research analyst with computation |

## Notes

- Agents are versioned: each `create_version` call increments the version number
- Conversations persist state across calls, so the agent remembers context
- Use `store=False` in the response call to opt out of statefulness when not needed
- The Responses API is synchronous -- no polling required (unlike the old Runs API)
- Agent definitions and conversation state use single-tenant storage for security
