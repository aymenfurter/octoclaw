/**
 * Azure Container Apps deployment target.
 *
 * Pushes the polyclaw image to Azure Container Registry, then creates
 * or updates an Azure Container App. The container lifecycle is NOT
 * tied to the CLI -- the app keeps running after the CLI exits.
 *
 * Supports reconnecting to a previously deployed container app
 * without rebuilding or redeploying.
 *
 * Prerequisites: `az` CLI installed and logged in.
 */

import { resolve } from "path";
import { randomBytes } from "crypto";
import type { AcaConfig, DeployResult, LogStream } from "../config/types.js";
import type { DeployTarget } from "./target.js";
import { exec, execStream, stripAzWarnings } from "./process.js";

const PROJECT_ROOT = resolve(import.meta.dir, "../../../..");

const CONFIG_PATH = resolve(
  process.env.HOME || "~",
  ".polyclaw-aca.json",
);

const DEPLOY_STATE_PATH = resolve(
  process.env.POLYCLAW_DATA_DIR || resolve(process.env.HOME || "~", ".polyclaw"),
  "deployments.json",
);

// ---------------------------------------------------------------------------
// Config persistence
// ---------------------------------------------------------------------------

async function loadConfig(): Promise<AcaConfig | null> {
  try {
    const file = Bun.file(CONFIG_PATH);
    if (await file.exists()) return await file.json();
  } catch { /* ignore */ }
  return null;
}

async function saveConfig(config: AcaConfig): Promise<void> {
  await Bun.write(CONFIG_PATH, JSON.stringify(config, null, 2));
  await syncDeployState(config);
}

function generateDeployId(): string {
  return randomBytes(4).toString("hex");
}

function deployTagFor(id: string): string {
  return `polycl-${id}`;
}

async function syncDeployState(config: AcaConfig): Promise<void> {
  let state: Record<string, unknown> & { deployments: Record<string, unknown> } = { deployments: {} };
  try {
    const f = Bun.file(DEPLOY_STATE_PATH);
    if (await f.exists()) state = await f.json() as typeof state;
  } catch { /* ignore */ }

  const now = new Date().toISOString();
  const existing = state.deployments?.[config.deployId] as Record<string, string> | undefined;

  state.deployments[config.deployId] = {
    deploy_id: config.deployId,
    tag: config.deployTag,
    kind: "aca",
    created_at: existing?.created_at || now,
    updated_at: now,
    status: "active",
    resource_groups: [config.resourceGroup],
    resources: [
      { resource_type: "acr", resource_group: config.resourceGroup, resource_name: config.acrName, resource_id: "", purpose: "Container Registry", created_at: existing?.created_at || now },
      { resource_type: "storage", resource_group: config.resourceGroup, resource_name: config.storageAccountName, resource_id: "", purpose: "NFS storage for persistent data", created_at: existing?.created_at || now },
      { resource_type: "aca", resource_group: config.resourceGroup, resource_name: config.appName, resource_id: "", purpose: "Container App", created_at: existing?.created_at || now },
    ],
    config: {
      fqdn: config.fqdn,
      acrLoginServer: config.acrLoginServer,
      environmentName: config.environmentName,
    },
  };

  const { mkdirSync } = await import("fs");
  const { dirname } = await import("path");
  try { mkdirSync(dirname(DEPLOY_STATE_PATH), { recursive: true }); } catch { /* ignore */ }
  await Bun.write(DEPLOY_STATE_PATH, JSON.stringify(state, null, 2) + "\n");
}

async function markDeployDestroyed(deployId: string): Promise<void> {
  try {
    const f = Bun.file(DEPLOY_STATE_PATH);
    if (!(await f.exists())) return;
    const state = await f.json() as Record<string, Record<string, Record<string, string>>>;
    if (state.deployments?.[deployId]) {
      state.deployments[deployId].status = "destroyed";
      state.deployments[deployId].updated_at = new Date().toISOString();
      await Bun.write(DEPLOY_STATE_PATH, JSON.stringify(state, null, 2) + "\n");
    }
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Preflight checks
// ---------------------------------------------------------------------------

export async function checkAzCliInstalled(): Promise<boolean> {
  try {
    const { exitCode } = await exec(["az", "version"]);
    return exitCode === 0;
  } catch {
    return false;
  }
}

export async function checkAzLoggedIn(): Promise<{ loggedIn: boolean; account?: string }> {
  try {
    const { stdout, exitCode } = await exec(["az", "account", "show", "--output", "json"]);
    if (exitCode !== 0) return { loggedIn: false };
    const data = JSON.parse(stdout);
    return {
      loggedIn: true,
      account: `${data.user?.name || "?"} (${data.name || data.id || "?"})`,
    };
  } catch {
    return { loggedIn: false };
  }
}

export async function getExistingDeployment(): Promise<AcaConfig | null> {
  const config = await loadConfig();
  if (!config) return null;

  try {
    const { exitCode } = await exec([
      "az", "containerapp", "show",
      "--name", config.appName,
      "--resource-group", config.resourceGroup,
      "--output", "none",
    ]);
    if (exitCode === 0) return config;
  } catch { /* ignore */ }
  return null;
}

// ---------------------------------------------------------------------------
// Remove deployment
// ---------------------------------------------------------------------------

export async function removeDeployment(
  onLine?: (line: string) => void,
): Promise<boolean> {
  const log = onLine || (() => {});
  const config = await loadConfig();
  if (!config) {
    log("No existing ACA deployment found.");
    return false;
  }

  log(`Removing Container App '${config.appName}' from resource group '${config.resourceGroup}'...`);

  const delOk = await execStream(
    ["az", "containerapp", "delete", "--name", config.appName, "--resource-group", config.resourceGroup, "--yes", "--output", "none"],
    onLine,
  );
  log(delOk ? "Container App deleted." : "Warning: Failed to delete Container App (it may already be gone).");

  log(`Deleting resource group '${config.resourceGroup}' and all resources...`);
  const rgOk = await execStream(
    ["az", "group", "delete", "--name", config.resourceGroup, "--yes", "--no-wait", "--output", "none"],
    onLine,
  );
  log(rgOk ? "Resource group deletion initiated (runs in background)." : "Warning: Failed to delete resource group.");

  try {
    const { unlinkSync } = require("fs");
    unlinkSync(CONFIG_PATH);
    log("Local config removed.");
  } catch { /* ignore */ }

  if (config.deployId) {
    await markDeployDestroyed(config.deployId);
    log(`Deployment ${config.deployId} marked as destroyed.`);
  }

  log("Deployment removed.");
  return true;
}

// ---------------------------------------------------------------------------
// ACA Deploy Target
// ---------------------------------------------------------------------------

export class AcaDeployTarget implements DeployTarget {
  readonly name = "Azure Container Apps";
  readonly lifecycleTied = false;

  private _config: AcaConfig | null = null;
  private _reconnect: boolean;

  constructor(reconnect = false) {
    this._reconnect = reconnect;
  }

  async deploy(
    adminPort: number,
    botPort: number,
    _mode: string,
    onLine?: (line: string) => void,
  ): Promise<DeployResult> {
    const log = onLine || (() => {});

    // -- Reconnect mode ---------------------------------------------------
    if (this._reconnect) {
      const existing = await loadConfig();
      if (!existing) throw new Error("No existing ACA deployment found. Deploy first.");

      log(`Reconnecting to ${existing.appName}...`);
      const baseUrl = `https://${existing.fqdn}`;

      const { exitCode } = await exec([
        "az", "containerapp", "show",
        "--name", existing.appName,
        "--resource-group", existing.resourceGroup,
        "--output", "none",
      ]);
      if (exitCode !== 0) {
        throw new Error(
          `Container app '${existing.appName}' not found. It may have been deleted. Deploy fresh instead.`,
        );
      }

      log(`Connected to ${existing.appName} at ${baseUrl}`);
      this._config = existing;
      return { baseUrl, instanceId: existing.appName, reconnected: true };
    }

    // -- Fresh deployment -------------------------------------------------
    const suffix = Date.now().toString(36).slice(-6);
    const prevConfig = await loadConfig();
    const deployId = prevConfig?.deployId || generateDeployId();
    const dtag = deployTagFor(deployId);
    const adminSecret = randomBytes(24).toString("base64url");

    const useRg = prevConfig?.resourceGroup || "polyclaw-acac-rg";
    const useLoc = prevConfig?.location || "eastus";
    const useAcrName = prevConfig?.acrName || `polyclawacr${suffix}`;
    const useEnv = prevConfig?.environmentName || "polyclaw-env";
    const useApp = prevConfig?.appName || "polyclaw";
    const useStorageAccount = prevConfig?.storageAccountName || `polyclawnfs${suffix}`;
    const useStorageShare = prevConfig?.storageShareName || "polyclawdata";
    const useVnet = prevConfig?.vnetName || "polyclaw-vnet";
    const useSubnet = prevConfig?.subnetName || "aca-subnet";
    const imageName = "polyclaw";
    const imageTag = "latest";

    // 1. Resource group
    log("Creating resource group...");
    if (!(await execStream(["az", "group", "create", "--name", useRg, "--location", useLoc, "--tags", `polyclaw_deploy=${dtag}`, "--output", "none"], onLine)))
      throw new Error("Failed to create resource group");

    // 2. ACR
    log("Ensuring Azure Container Registry...");
    const acrCheck = await exec(["az", "acr", "show", "--name", useAcrName, "--resource-group", useRg, "--output", "json"]);
    let loginServer: string;
    if (acrCheck.exitCode === 0) {
      loginServer = JSON.parse(acrCheck.stdout).loginServer;
      log(`Using existing ACR: ${loginServer}`);
    } else {
      log("Creating ACR (this may take a minute)...");
      if (!(await execStream(["az", "acr", "create", "--resource-group", useRg, "--name", useAcrName, "--sku", "Basic", "--admin-enabled", "true", "--output", "json"], onLine)))
        throw new Error("Failed to create Azure Container Registry");
      const acrShow = await exec(["az", "acr", "show", "--name", useAcrName, "--resource-group", useRg, "--output", "json"]);
      if (acrShow.exitCode !== 0) throw new Error("Failed to get ACR details");
      loginServer = JSON.parse(acrShow.stdout).loginServer;
    }

    // 3. Build image
    log("Building Docker image (linux/amd64)...");
    if (!(await execStream(["docker", "build", "--platform", "linux/amd64", "--progress=plain", "-t", `${loginServer}/${imageName}:${imageTag}`, "."], onLine, PROJECT_ROOT)))
      throw new Error("Docker build failed");

    // 4. Push to ACR
    log("Logging in to ACR...");
    if (!(await execStream(["az", "acr", "login", "--name", useAcrName], onLine)))
      throw new Error("Failed to log in to ACR");

    log("Pushing image to ACR (this may take several minutes)...");
    if (!(await execStream(["docker", "push", `${loginServer}/${imageName}:${imageTag}`], onLine)))
      throw new Error("Failed to push image to ACR");

    // 5a. VNet
    log("Ensuring VNet for Container Apps environment...");
    const vnetCheck = await exec(["az", "network", "vnet", "show", "--name", useVnet, "--resource-group", useRg, "--output", "none"]);
    if (vnetCheck.exitCode !== 0) {
      log("Creating VNet and subnet...");
      if (!(await execStream(["az", "network", "vnet", "create", "--name", useVnet, "--resource-group", useRg, "--location", useLoc, "--address-prefix", "10.0.0.0/16", "--subnet-name", useSubnet, "--subnet-prefix", "10.0.0.0/23", "--output", "none"], onLine)))
        throw new Error("Failed to create VNet");
      await execStream(["az", "network", "vnet", "subnet", "update", "--vnet-name", useVnet, "--resource-group", useRg, "--name", useSubnet, "--service-endpoints", "Microsoft.Storage", "--delegations", "Microsoft.App/environments", "--output", "none"], onLine);
    }

    const subnetIdResult = await exec(["az", "network", "vnet", "subnet", "show", "--vnet-name", useVnet, "--resource-group", useRg, "--name", useSubnet, "--query", "id", "--output", "tsv"]);
    if (subnetIdResult.exitCode !== 0 || !subnetIdResult.stdout) throw new Error("Failed to get subnet resource ID");
    const subnetId = subnetIdResult.stdout.trim();

    // 5b. Storage account
    log("Ensuring Premium FileStorage account for NFS...");
    const stCheck = await exec(["az", "storage", "account", "show", "--name", useStorageAccount, "--resource-group", useRg, "--output", "none"]);
    if (stCheck.exitCode !== 0) {
      log("Creating Premium FileStorage account (this may take a minute)...");
      if (!(await execStream(["az", "storage", "account", "create", "--name", useStorageAccount, "--resource-group", useRg, "--location", useLoc, "--sku", "Premium_LRS", "--kind", "FileStorage", "--https-only", "false", "--output", "none"], onLine)))
        throw new Error("Failed to create FileStorage account");
      await execStream(["az", "storage", "account", "network-rule", "add", "--resource-group", useRg, "--account-name", useStorageAccount, "--vnet-name", useVnet, "--subnet", useSubnet, "--output", "none"], onLine);
      await exec(["az", "storage", "account", "update", "--resource-group", useRg, "--name", useStorageAccount, "--default-action", "Deny", "--output", "none"]);
    } else {
      log(`Using existing FileStorage account: ${useStorageAccount}`);
    }

    // NFS file share
    log("Ensuring NFS file share...");
    const shareCheck = await exec(["az", "storage", "share-rm", "show", "--name", useStorageShare, "--storage-account", useStorageAccount, "--resource-group", useRg, "--output", "none"]);
    if (shareCheck.exitCode !== 0) {
      if (!(await execStream(["az", "storage", "share-rm", "create", "--name", useStorageShare, "--storage-account", useStorageAccount, "--resource-group", useRg, "--enabled-protocols", "NFS", "--quota", "100", "--output", "none"], onLine)))
        throw new Error("Failed to create NFS file share");
    }

    // 5c. ACA environment
    log("Ensuring Container Apps environment...");
    const envCheck = await exec(["az", "containerapp", "env", "show", "--name", useEnv, "--resource-group", useRg, "--output", "none"]);
    if (envCheck.exitCode !== 0) {
      log("Creating Container Apps environment with VNet (this may take a few minutes)...");
      if (!(await execStream(["az", "containerapp", "env", "create", "--name", useEnv, "--resource-group", useRg, "--location", useLoc, "--infrastructure-subnet-resource-id", subnetId, "--output", "none"], onLine)))
        throw new Error("Failed to create Container Apps environment");
    }

    // NFS storage link
    const storageLinkName = "polyclawdata";
    log("Linking NFS storage to Container Apps environment...");
    const envIdResult = await exec(["az", "containerapp", "env", "show", "--name", useEnv, "--resource-group", useRg, "--query", "id", "--output", "tsv"]);
    if (envIdResult.exitCode !== 0 || !envIdResult.stdout) throw new Error("Failed to get ACA environment resource ID");
    const envId = stripAzWarnings(envIdResult.stdout);

    const nfsLinkBody = JSON.stringify({
      properties: {
        nfsAzureFile: {
          server: `${useStorageAccount}.file.core.windows.net`,
          shareName: `/${useStorageAccount}/${useStorageShare}`,
          accessMode: "ReadWrite",
        },
      },
    });
    const nfsLinkPath = `/tmp/polyclaw-nfs-link-${Date.now()}.json`;
    await Bun.write(nfsLinkPath, nfsLinkBody);

    const storageApiUrl = `https://management.azure.com${envId}/storages/${storageLinkName}?api-version=2023-11-02-preview`;
    const linkResult = await exec(["az", "rest", "--method", "put", "--url", storageApiUrl, "--body", `@${nfsLinkPath}`, "--output", "json"]);
    if (linkResult.exitCode !== 0) throw new Error(`Failed to link NFS storage: ${linkResult.stderr}`);

    // ACR credentials
    const credResult = await exec(["az", "acr", "credential", "show", "--name", useAcrName, "--output", "json"]);
    if (credResult.exitCode !== 0) throw new Error("Failed to get ACR credentials");
    const creds = JSON.parse(credResult.stdout);
    const acrUsername = creds.username;
    const acrPassword = creds.passwords?.[0]?.value || "";

    // 6. Delete existing + create container app
    const appCheck = await exec(["az", "containerapp", "show", "--name", useApp, "--resource-group", useRg, "--output", "none"]);
    if (appCheck.exitCode === 0) {
      log("Deleting existing Container App for a clean deploy...");
      await execStream(["az", "containerapp", "delete", "--name", useApp, "--resource-group", useRg, "--yes", "--output", "none"], onLine);
    }

    const volumeName = "data-volume";
    log("Creating Container App...");
    if (!(await execStream([
      "az", "containerapp", "create",
      "--name", useApp, "--resource-group", useRg, "--environment", useEnv,
      "--image", `${loginServer}/${imageName}:${imageTag}`,
      "--registry-server", loginServer,
      "--registry-username", acrUsername, "--registry-password", acrPassword,
      "--target-port", String(adminPort), "--ingress", "external",
      "--cpu", "1", "--memory", "2Gi",
      "--min-replicas", "1", "--max-replicas", "1",
      "--env-vars", `ADMIN_PORT=${adminPort}`, "POLYCLAW_CONTAINER=1", "POLYCLAW_DATA_DIR=/data", `ADMIN_SECRET=${adminSecret}`,
      "--output", "none",
    ], onLine)))
      throw new Error("Failed to create Container App");

    // NFS volume mount via exported spec
    log("Configuring persistent NFS storage volume...");
    const exportResult = await exec(["az", "containerapp", "show", "--name", useApp, "--resource-group", useRg, "--output", "json"]);
    if (exportResult.exitCode !== 0) throw new Error("Failed to export Container App spec for volume setup");

    const appSpec = JSON.parse(stripAzWarnings(exportResult.stdout));
    appSpec.properties.template.volumes = [{ name: volumeName, storageType: "NfsAzureFile", storageName: storageLinkName }];
    for (const container of appSpec.properties.template.containers) {
      container.volumeMounts = [{ volumeName, mountPath: "/data" }];
    }

    const updateSpecPath = `/tmp/polyclaw-aca-update-${Date.now()}.json`;
    await Bun.write(updateSpecPath, JSON.stringify(appSpec, null, 2));

    if (!(await execStream(["az", "containerapp", "update", "--name", useApp, "--resource-group", useRg, "--yaml", updateSpecPath, "--output", "none"], onLine)))
      throw new Error("Failed to configure NFS storage on Container App");

    const verifyResult = await exec(["az", "containerapp", "show", "--name", useApp, "--resource-group", useRg, "--query", "properties.template.volumes[0].storageName", "--output", "tsv"]);
    log(stripAzWarnings(verifyResult.stdout) === storageLinkName
      ? "Persistent NFS storage volume configured successfully."
      : "WARNING: Volume mount may not have been applied correctly.");

    // Restart revision
    log("Restarting revision to activate NFS mount...");
    const revResult = await exec(["az", "containerapp", "revision", "list", "--name", useApp, "--resource-group", useRg, "--query", "[?properties.trafficWeight>0].name | [0]", "--output", "tsv"]);
    const activeRevision = stripAzWarnings(revResult.stdout);
    if (activeRevision) {
      await execStream(["az", "containerapp", "revision", "restart", "--name", useApp, "--resource-group", useRg, "--revision", activeRevision, "--output", "none"], onLine);
      log("Waiting for container to come back up...");
      await Bun.sleep(15_000);
    }

    // 7. Get FQDN
    log("Getting deployment URL...");
    const showResult = await exec(["az", "containerapp", "show", "--name", useApp, "--resource-group", useRg, "--query", "properties.configuration.ingress.fqdn", "--output", "tsv"]);
    if (showResult.exitCode !== 0 || !showResult.stdout) throw new Error("Failed to get Container App FQDN");
    const fqdn = stripAzWarnings(showResult.stdout);
    const baseUrl = `https://${fqdn}`;

    this._config = {
      deployId, deployTag: dtag,
      resourceGroup: useRg, location: useLoc,
      acrName: useAcrName, acrLoginServer: loginServer,
      environmentName: useEnv, appName: useApp, fqdn,
      storageAccountName: useStorageAccount, storageShareName: useStorageShare,
      vnetName: useVnet, subnetName: useSubnet,
      adminPort, botPort, adminSecret,
      lastDeployed: new Date().toISOString(),
    };
    await saveConfig(this._config);

    log(`Deployed to ${baseUrl}`);
    return { baseUrl, instanceId: useApp, reconnected: false };
  }

  streamLogs(instanceId: string, onLine: (line: string) => void): LogStream {
    const rg = this._config?.resourceGroup || "polyclaw-acac-rg";
    const proc = Bun.spawn(
      ["az", "containerapp", "logs", "show", "--name", instanceId, "--resource-group", rg, "--type", "console", "--follow", "--tail", "50"],
      { stdout: "pipe", stderr: "pipe" },
    );

    let stopped = false;

    const extractLogMessage = (raw: string): string => {
      const trimmed = raw.trim();
      if (trimmed.startsWith("{")) {
        try {
          const parsed = JSON.parse(trimmed);
          if (parsed.Log != null) return String(parsed.Log).replace(/\n$/, "");
        } catch { /* fallback */ }
      }
      return trimmed;
    };

    const drain = async (stream: ReadableStream<Uint8Array> | null) => {
      if (!stream) return;
      const reader = stream.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      try {
        while (!stopped) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() || "";
          for (const line of lines) {
            const msg = extractLogMessage(line);
            if (msg) onLine(msg);
          }
        }
        if (buffer.trim()) onLine(extractLogMessage(buffer));
      } catch { /* killed */ }
    };

    drain(proc.stdout as ReadableStream<Uint8Array>);
    drain(proc.stderr as ReadableStream<Uint8Array>);

    return {
      stop() {
        stopped = true;
        try { proc.kill(); } catch { /* ignore */ }
      },
    };
  }

  async waitForReady(baseUrl: string, timeoutMs = 300_000): Promise<boolean> {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        const res = await fetch(`${baseUrl}/health`, { signal: AbortSignal.timeout(5000) });
        if (res.ok) return true;
      } catch { /* not ready */ }
      await Bun.sleep(3000);
    }
    return false;
  }

  async disconnect(_instanceId: string): Promise<void> {
    // ACA: container keeps running -- nothing to do.
  }

  async getAdminSecret(_instanceId?: string): Promise<string> {
    if (this._config?.adminSecret) return this._config.adminSecret;
    const config = await loadConfig();
    return config?.adminSecret || "";
  }

  async resolveKvSecret(secret: string, _instanceId?: string): Promise<string> {
    return secret.startsWith("@kv:") ? "" : secret;
  }
}
