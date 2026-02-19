/**
 * Polyclaw TUI -- entry point.
 *
 * Admin mode: launches the interactive TUI (disclaimer -> target picker
 *             -> deploy lifecycle & chat).
 *
 * Bot mode:   headless -- Docker build, run, block until Ctrl-C.
 */

import {
  buildImage,
  startContainer,
  getAdminSecret,
  resolveKvSecret,
  waitForReady,
  stopContainer,
} from "./deploy/docker.js";
import { launchTUI } from "./ui/tui.js";
import { showDisclaimer } from "./ui/disclaimer.js";
import { pickDeployTarget } from "./ui/target-picker.js";

// -----------------------------------------------------------------------
// Help
// -----------------------------------------------------------------------

function usage(): void {
  console.log("Usage: polyclaw-cli [admin|bot]");
  console.log("");
  console.log("  admin  - TUI with status dashboard and chat (default)");
  console.log("  bot    - Bot Framework server only (headless)");
  console.log("");
}

// -----------------------------------------------------------------------
// Main
// -----------------------------------------------------------------------

async function main(): Promise<void> {
  const mode = process.argv[2] || "admin";

  if (mode === "-h" || mode === "--help") {
    usage();
    process.exit(0);
  }

  if (!["admin", "bot"].includes(mode)) {
    console.error(`Unknown mode: ${mode}`);
    usage();
    process.exit(1);
  }

  const adminPort = parseInt(process.env.ADMIN_PORT || "8080", 10);
  const botPort = parseInt(process.env.BOT_PORT || "3978", 10);

  // ---- Admin TUI mode ---------------------------------------------------
  if (mode === "admin") {
    await showDisclaimer();

    const target = await pickDeployTarget(adminPort, botPort);
    await launchTUI(adminPort, botPort, target);
    return;
  }

  // ---- Bot-only mode (headless) -----------------------------------------
  console.log("Building polyclaw v3...");
  console.log("");

  const buildOk = await buildImage();
  if (!buildOk) {
    console.error("Build failed.");
    process.exit(1);
  }

  console.log("Starting polyclaw...");
  let containerId: string;
  try {
    containerId = await startContainer(adminPort, botPort, "bot");
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err);
    console.error("Failed to start container:", msg);
    process.exit(1);
  }

  let secret = await getAdminSecret();
  if (secret.startsWith("@kv:")) {
    secret = await resolveKvSecret(secret);
  }

  const adminUrl = secret
    ? `http://localhost:${adminPort}/?secret=${secret}`
    : `http://localhost:${adminPort}`;

  console.log(`Bot running on port ${botPort}`);
  console.log(`Admin: ${adminUrl}`);
  console.log("");

  const shutdown = async () => {
    console.log("\nStopping...");
    await stopContainer(containerId);
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  console.log("Waiting for server...");
  const ready = await waitForReady(`http://localhost:${adminPort}`);
  if (!ready) {
    console.error("Server did not become ready.");
    await stopContainer(containerId);
    process.exit(1);
  }
  console.log("Server is ready. Press Ctrl+C to stop.");
  await new Promise(() => {});
}

main().catch((err: unknown) => {
  const msg = err instanceof Error ? err.message : String(err);
  console.error("Fatal:", msg);
  process.exit(1);
});
