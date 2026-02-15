---
name: foundry-code-interpreter
description: |
  Create an ad-hoc Microsoft Foundry agent with Code Interpreter to analyze data,
  generate charts, solve math problems, or run Python code in a sandboxed environment.
  Uses the new Foundry v2 Responses API with conversations.
  Use when the user says: "analyze this data", "create a chart", "run code interpreter",
  "foundry code interpreter", "analyze csv", "generate a plot", "solve this with code",
  "use code interpreter", "data analysis agent"
metadata:
  verb: analyze
---

# Foundry Code Interpreter Agent

Create an ad-hoc Foundry agent with Code Interpreter enabled using the new v2 Responses API.

The agent can write and execute Python code in a sandboxed environment to solve data analysis tasks, generate visualizations, and perform computations.

## Prerequisites

The user must have completed the Foundry setup (the `setup-foundry` skill). They need:
- `FOUNDRY_PROJECT_ENDPOINT` -- the project endpoint URL
- `FOUNDRY_MODEL_DEPLOYMENT_NAME` -- the model deployment name (e.g. `gpt-4.1-mini`)

If these are not set, ask the user for the values.

## Steps

### 1. Determine the Task

Ask the user what they want the code interpreter agent to do. Examples:
- "Analyze this CSV file and create a bar chart"
- "Solve this equation: sin(x) + x^2 = 42"
- "Generate a histogram of this data"
- "Calculate statistics for this dataset"

If the user provides a file, note the file path for upload.

### 2. Run the Code Interpreter Agent

Use the following Python script. Replace placeholders with actual values.

**Without file upload (computation / code generation):**

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool, CodeInterpreterToolAuto

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")
model = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "<MODEL>")

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    openai_client = project_client.get_openai_client()

    # Create agent with code interpreter
    agent = project_client.agents.create_version(
        agent_name="CodeInterpreterAgent",
        definition=PromptAgentDefinition(
            model=model,
            instructions="You are a data analysis and computation assistant. Write and execute Python code to solve the user's problem. Show results clearly.",
            tools=[CodeInterpreterTool(container=CodeInterpreterToolAuto())],
        ),
        description="Ad-hoc code interpreter agent.",
    )
    print(f"Agent created: {agent.name} v{agent.version}")

    # Create a conversation
    conversation = openai_client.conversations.create()
    print(f"Conversation: {conversation.id}")

    # Send the user's request
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="USER_PROMPT_HERE",
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

**With file upload (data analysis):**

```bash
python3 << 'PYEOF'
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient
from azure.ai.projects.models import PromptAgentDefinition, CodeInterpreterTool, CodeInterpreterToolAuto

endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT", "<ENDPOINT>")
model = os.environ.get("FOUNDRY_MODEL_DEPLOYMENT_NAME", "<MODEL>")
file_path = "FILE_PATH_HERE"

project_client = AIProjectClient(
    endpoint=endpoint,
    credential=DefaultAzureCredential(),
)

with project_client:
    openai_client = project_client.get_openai_client()

    # Upload the file
    with open(file_path, "rb") as f:
        uploaded_file = openai_client.files.create(purpose="assistants", file=f)
    print(f"File uploaded: {uploaded_file.id}")

    # Create agent with code interpreter and file access
    agent = project_client.agents.create_version(
        agent_name="DataAnalysisAgent",
        definition=PromptAgentDefinition(
            model=model,
            instructions="You are a data analysis assistant. Analyze the uploaded file and fulfil the user's request. Generate charts or output files when appropriate.",
            tools=[CodeInterpreterTool(container=CodeInterpreterToolAuto(file_ids=[uploaded_file.id]))],
        ),
        description="Ad-hoc data analysis agent with file.",
    )
    print(f"Agent created: {agent.name} v{agent.version}")

    # Create a conversation
    conversation = openai_client.conversations.create()

    # Send the user's request
    response = openai_client.responses.create(
        conversation=conversation.id,
        input="USER_PROMPT_HERE",
        extra_body={"agent": {"name": agent.name, "type": "agent_reference"}},
    )

    # Print response and download generated files
    for item in response.output:
        if item.type == "message":
            for content in item.content:
                if content.type == "output_text":
                    print(content.text)
                    # Check for file citations
                    if hasattr(content, "annotations") and content.annotations:
                        for ann in content.annotations:
                            if ann.type == "container_file_citation":
                                file_content = openai_client.containers.files.content.retrieve(
                                    file_id=ann.file_id, container_id=ann.container_id
                                )
                                safe_name = os.path.basename(ann.filename)
                                with open(safe_name, "wb") as out:
                                    out.write(file_content.read())
                                print(f"Downloaded: {safe_name}")

    # Clean up
    project_client.agents.delete_version(agent_name=agent.name, agent_version=agent.version)
    print("Agent cleaned up.")
PYEOF
```

### 3. Present Results

After running the script:
- Show the text output from the agent
- If files were generated (charts, CSVs), tell the user where they were saved
- If there were errors, explain what went wrong and suggest fixes

### 4. Follow-up

The conversation is stateful. If the user wants to continue the analysis, reuse the same conversation ID and agent. Only clean up when the user is done.

## Supported File Types

The code interpreter supports: `.csv`, `.json`, `.xlsx`, `.txt`, `.pdf`, `.py`, `.md`, `.html`, `.png`, `.jpg`, `.gif`, and more.

## Notes

- Code Interpreter runs Python in a sandboxed container with common data science packages (pandas, matplotlib, numpy, etc.)
- Each session is active for 1 hour with a 30-minute idle timeout
- Additional charges apply beyond standard token-based fees
- For custom packages, a custom code interpreter container can be configured
