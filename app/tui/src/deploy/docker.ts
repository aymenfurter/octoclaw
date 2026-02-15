/**
 * Local Docker deployment target.
 *
 * Builds the image locally, runs a container, and ties the container
 * lifecycle to the CLI process (container stops on exit).
 */

import { resolve } from "path";
import type { DeployResult, LogStream } from "../config/types.js";
import type { DeployTarget } from "./target.js";
import { exec, execStream } from "./process.js";

/** Repository root -- two levels up from `app/tui/src/deploy/`. */
const PROJECT_ROOT = resolve(import.meta.dir, "../../../..");

// ---------------------------------------------------------------------------
// Standalone functions (also used by the headless bot-only mode)
// ---------------------------------------------------------------------------

/**
 * Build the Docker image.
 *
 * When `onLine` is provided, stdout/stderr are piped and forwarded
 * line-by-line. Without it, output is inherited directly.
 */
export async function buildImage(
  onLine?: (line: string) => void,
): Promise<boolean> {
  return execStream(
    ["docker", "build", "--progress=plain", "-t", "octoclaw", "."],
    onLine,
    PROJECT_ROOT,
  );
}

/** Kill any existing containers bound to the given ports. */
export async function killExisting(adminPort: number, botPort: number): Promise<void> {
  try {
    const { stdout } = await exec([
      "docker", "ps",
      "--filter", `publish=${adminPort}`,
      "--filter", `publish=${botPort}`,
      "-q",
    ]);
    if (stdout) {
      for (const id of stdout.split("\n").filter(Boolean)) {
        await exec(["docker", "rm", "-f", id]);
      }
    }
  } catch {
    // Ignore errors when no containers found
  }
}

/** Start a container in detached mode and return its ID. */
export async function startContainer(
  adminPort: number,
  botPort: number,
  mode: string,
): Promise<string> {
  await killExisting(adminPort, botPort);

  const args = [
    "docker", "run", "-d", "--rm",
    "-v", "octoclaw-data:/data",
    "-p", `${adminPort}:${adminPort}`,
    "-p", `${botPort}:${botPort}`,
    "-e", `ADMIN_PORT=${adminPort}`,
  ];

  if (mode === "bot") {
    args.push("-e", "OCTOCLAW_MODE=bot");
  }

  args.push("octoclaw");

  const { stdout, exitCode } = await exec(args);
  if (exitCode !== 0) {
    throw new Error(`docker run exited with code ${exitCode}`);
  }
  return stdout;
}

/** Stop a running container by ID. */
export async function stopContainer(containerId: string): Promise<void> {
  if (!containerId) return;
  try {
    await exec(["docker", "stop", containerId]);
  } catch {
    // Container may already be stopped
  }
}

/** Read the admin secret from the Docker data volume. */
export async function getAdminSecret(): Promise<string> {
  try {
    const { stdout, exitCode } = await exec([
      "docker", "run", "--rm",
      "-v", "octoclaw-data:/data",
      "alpine", "cat", "/data/.env",
    ]);
    if (exitCode !== 0) return "";
    const match = stdout.match(/^ADMIN_SECRET=(.+)$/m);
    return match ? match[1].replace(/"/g, "").trim() : "";
  } catch {
    return "";
  }
}

/**
 * Resolve a `@kv:...` secret reference.
 *
 * When `containerId` is provided, uses `docker exec` on the running
 * container. Falls back to `docker run` with a fresh container.
 */
export async function resolveKvSecret(
  secret: string,
  containerId?: string,
): Promise<string> {
  if (!secret.startsWith("@kv:")) return secret;

  const script = [
    "import os, sys",
    "os.environ['OCTOCLAW_DATA_DIR'] = '/data'",
    "from dotenv import load_dotenv",
    "load_dotenv('/data/.env', override=True)",
    "from octoclaw.keyvault import kv, is_kv_ref",
    "v = os.getenv('ADMIN_SECRET', '')",
    "if is_kv_ref(v):",
    "    print(kv.resolve_value(v), end='')",
    "else:",
    "    print(v, end='')",
  ].join("\n");

  if (containerId) {
    try {
      const { stdout, exitCode } = await exec([
        "docker", "exec", containerId, "python", "-c", script,
      ]);
      if (exitCode === 0 && stdout) return stdout;
    } catch { /* fall through */ }
  }

  try {
    const { stdout, exitCode } = await exec([
      "docker", "run", "--rm",
      "-v", "octoclaw-data:/data",
      "octoclaw", "python", "-c", script,
    ]);
    if (exitCode === 0 && stdout) return stdout;
  } catch { /* ignore */ }

  return "";
}

/** Stream `docker logs -f` for a container. */
export function streamContainerLogs(
  containerId: string,
  onLine: (line: string) => void,
): LogStream {
  const proc = Bun.spawn(
    ["docker", "logs", "-f", "--tail", "50", containerId],
    { stdout: "pipe", stderr: "pipe" },
  );

  let stopped = false;

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
          if (line.trim()) onLine(line);
        }
      }
      if (buffer.trim()) onLine(buffer);
    } catch {
      // Process was killed
    }
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

/** Poll the health endpoint until it responds 200. */
export async function waitForReady(
  baseUrl: string,
  timeoutMs = 300_000,
): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${baseUrl}/health`, {
        signal: AbortSignal.timeout(2000),
      });
      if (res.ok) return true;
    } catch {
      // Server not ready yet
    }
    await Bun.sleep(1500);
  }
  return false;
}

// ---------------------------------------------------------------------------
// DeployTarget implementation
// ---------------------------------------------------------------------------

export class DockerDeployTarget implements DeployTarget {
  readonly name = "Local Docker";
  readonly lifecycleTied = true;

  async deploy(
    adminPort: number,
    botPort: number,
    mode: string,
    onLine?: (line: string) => void,
  ): Promise<DeployResult> {
    const buildOk = await buildImage(onLine);
    if (!buildOk) throw new Error("Docker build failed");

    const containerId = await startContainer(adminPort, botPort, mode);
    return {
      baseUrl: `http://localhost:${adminPort}`,
      instanceId: containerId,
      reconnected: false,
    };
  }

  streamLogs(instanceId: string, onLine: (line: string) => void): LogStream {
    return streamContainerLogs(instanceId, onLine);
  }

  async waitForReady(baseUrl: string, timeoutMs?: number): Promise<boolean> {
    return waitForReady(baseUrl, timeoutMs);
  }

  async disconnect(instanceId: string): Promise<void> {
    await stopContainer(instanceId);
  }

  async getAdminSecret(_instanceId?: string): Promise<string> {
    return getAdminSecret();
  }

  async resolveKvSecret(secret: string, instanceId?: string): Promise<string> {
    return resolveKvSecret(secret, instanceId);
  }
}
