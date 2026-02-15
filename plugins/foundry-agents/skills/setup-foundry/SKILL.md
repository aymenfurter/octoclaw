---
name: setup-foundry
description: |
  Provision a Microsoft Foundry resource, create a project, deploy a model (gpt-4.1-mini),
  and install the required Python SDK packages. This is a one-time setup skill.
  Use when the user says: "setup foundry", "provision foundry", "create foundry resource",
  "setup azure ai foundry", "install foundry sdk"
metadata:
  verb: setup
---

# Microsoft Foundry Setup

Provision a Foundry resource, project, and model deployment via Azure CLI, then install the Python SDK.

## Step 1 -- Verify Azure CLI

```bash
az version --output table
```

If the CLI is not installed, tell the user to install it from https://learn.microsoft.com/cli/azure/install-azure-cli and come back.

## Step 2 -- Authenticate

```bash
az account show --output table
```

If not logged in, run:

```bash
az login
```

## Step 3 -- Choose Configuration

Ask the user for the following values (or offer sensible defaults):

| Setting | Default |
|---------|---------|
| Resource group name | `foundry-agents-rg` |
| Foundry resource name | `foundry-<username>` (must be globally unique) |
| Project name | `default` |
| Location | `eastus` |
| Model to deploy | `gpt-4.1-mini` |
| Deployment name | `gpt-4.1-mini` |

## Step 4 -- Create the Resource Group

```bash
az group create --name <RESOURCE_GROUP> --location <LOCATION>
```

## Step 5 -- Create the Foundry Resource

```bash
az cognitiveservices account create \
    --name <FOUNDRY_RESOURCE_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --kind AIServices \
    --sku S0 \
    --location <LOCATION> \
    --allow-project-management \
    --yes
```

## Step 6 -- Set a Custom Subdomain

The custom subdomain is required for SDK access. It must be globally unique.

```bash
az cognitiveservices account update \
    --name <FOUNDRY_RESOURCE_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --custom-domain <FOUNDRY_RESOURCE_NAME>
```

## Step 7 -- Create the Project

```bash
az cognitiveservices account project create \
    --name <FOUNDRY_RESOURCE_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --project-name <PROJECT_NAME> \
    --location <LOCATION>
```

## Step 8 -- Deploy a Model

```bash
az cognitiveservices account deployment create \
    --name <FOUNDRY_RESOURCE_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --deployment-name <DEPLOYMENT_NAME> \
    --model-name <MODEL_NAME> \
    --model-version "2025-04-14" \
    --model-format OpenAI \
    --sku-capacity 10 \
    --sku-name GlobalStandard
```

If the model version or SKU is not available in the selected region, try `Standard` SKU or a different model version. You can list available models with:

```bash
az cognitiveservices account list-models \
    --name <FOUNDRY_RESOURCE_NAME> \
    --resource-group <RESOURCE_GROUP> \
    --output table
```

## Step 9 -- Install the Python SDK

```bash
pip install azure-ai-projects --pre openai azure-identity python-dotenv
```

## Step 10 -- Verify the Setup

Build the project endpoint from the resource and project names:

```
https://<FOUNDRY_RESOURCE_NAME>.services.ai.azure.com/api/projects/<PROJECT_NAME>
```

Run a quick verification:

```bash
python3 -c "
import os
from azure.identity import DefaultAzureCredential
from azure.ai.projects import AIProjectClient

endpoint = 'https://<FOUNDRY_RESOURCE_NAME>.services.ai.azure.com/api/projects/<PROJECT_NAME>'
client = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
openai_client = client.get_openai_client()
resp = openai_client.responses.create(
    model='<DEPLOYMENT_NAME>',
    input='Say hello in one sentence.',
)
print('Model response:', resp.output_text)
print('Setup verified successfully.')
"
```

Replace the placeholders with the actual values chosen earlier.

## Step 11 -- Save Environment Variables

Tell the user to note down or export these values for future use:

```bash
export FOUNDRY_PROJECT_ENDPOINT="https://<FOUNDRY_RESOURCE_NAME>.services.ai.azure.com/api/projects/<PROJECT_NAME>"
export FOUNDRY_MODEL_DEPLOYMENT_NAME="<DEPLOYMENT_NAME>"
```

## Summary

Tell the user:
- The Foundry resource, project, and model deployment are ready
- The project endpoint URL (they will need it for the other skills)
- The model deployment name
- The Python SDK packages are installed
- They can now use the Foundry Code Interpreter and Foundry Agent Chat skills
