/**
 * Deployment target interface.
 *
 * Abstracts the container lifecycle so the TUI can orchestrate build,
 * deploy, health-check, logs, and teardown without knowing whether
 * the backend is local Docker or Azure Container Apps.
 */

import type { DeployResult, LogStream } from "../config/types.js";

export type TargetType = "docker" | "aca";

export interface DeployTarget {
  /** Human-readable label shown in the TUI. */
  readonly name: string;

  /**
   * Whether the container lifecycle is tied to the CLI process.
   *
   * `true`  -- local Docker: container stops when CLI exits.
   * `false` -- ACA: container keeps running after CLI exits.
   */
  readonly lifecycleTied: boolean;

  /** Build and deploy the container, streaming progress via `onLine`. */
  deploy(
    adminPort: number,
    botPort: number,
    mode: string,
    onLine?: (line: string) => void,
  ): Promise<DeployResult>;

  /** Stream logs from the running instance. */
  streamLogs(instanceId: string, onLine: (line: string) => void): LogStream;

  /** Wait for the server to become healthy. */
  waitForReady(baseUrl: string, timeoutMs?: number): Promise<boolean>;

  /** Disconnect from (or stop) the running instance. */
  disconnect(instanceId: string): Promise<void>;

  /** Read the admin secret from the persistent data volume. */
  getAdminSecret(instanceId?: string): Promise<string>;

  /** Resolve a `@kv:...` secret reference. */
  resolveKvSecret(secret: string, instanceId?: string): Promise<string>;
}
