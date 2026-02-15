/**
 * Dashboard screen -- overview of system status.
 */

import {
  BoxRenderable,
  TextRenderable,
  ScrollBoxRenderable,
} from "@opentui/core";
import { Screen } from "./screen.js";
import { Colors } from "../utils/theme.js";

export class DashboardScreen extends Screen {
  private statusText!: TextRenderable;
  private modelText!: TextRenderable;
  private tunnelText!: TextRenderable;

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    const statusBox = new BoxRenderable(this.renderer, {
      border: true,
      borderColor: Colors.border,
      title: " System Status ",
      backgroundColor: Colors.surface,
      width: "100%",
      padding: 1,
      flexDirection: "column",
    });

    this.statusText = new TextRenderable(this.renderer, {
      content: "Loading...",
      fg: Colors.muted,
      width: "100%",
    });
    statusBox.add(this.statusText);
    this.container.add(statusBox);

    const modelBox = new BoxRenderable(this.renderer, {
      border: true,
      borderColor: Colors.border,
      title: " Model ",
      backgroundColor: Colors.surface,
      width: "100%",
      padding: 1,
      flexDirection: "column",
    });

    this.modelText = new TextRenderable(this.renderer, {
      content: "Loading...",
      fg: Colors.muted,
      width: "100%",
    });
    modelBox.add(this.modelText);
    this.container.add(modelBox);

    const tunnelBox = new BoxRenderable(this.renderer, {
      border: true,
      borderColor: Colors.border,
      title: " Tunnel ",
      backgroundColor: Colors.surface,
      width: "100%",
      padding: 1,
      flexDirection: "column",
    });

    this.tunnelText = new TextRenderable(this.renderer, {
      content: "Loading...",
      fg: Colors.muted,
      width: "100%",
    });
    tunnelBox.add(this.tunnelText);
    this.container.add(tunnelBox);
  }

  refresh(): void {
    this.loadStatus();
  }

  private async loadStatus(): Promise<void> {
    try {
      const s = await this.api.getSetupStatus();

      const dot = (ok: boolean) => ok ? "\x1b[32m●\x1b[0m" : "\x1b[31m●\x1b[0m";
      const azOk = s.azure?.logged_in ?? false;
      const ghOk = s.copilot?.authenticated ?? false;
      const tunnelOk = s.tunnel?.active ?? false;
      const botOk = s.bot_configured ?? false;
      const voiceOk = s.voice_call_configured ?? false;

      this.statusText.content = [
        `  ${dot(azOk)} Azure     ${azOk ? (s.azure?.user ?? "Logged in") : "Not logged in"}`,
        `  ${dot(ghOk)} GitHub    ${ghOk ? (s.copilot?.details ?? "Authenticated") : "Not authenticated"}`,
        `  ${dot(tunnelOk)} Tunnel    ${tunnelOk ? (s.tunnel?.url ?? "Active") : "Inactive"}`,
        `  ${dot(botOk)} Bot       ${botOk ? "Configured" : "Not configured"}`,
        `  ${dot(voiceOk)} Voice     ${voiceOk ? "Configured" : "Not configured"}`,
      ].join("\n");

      this.modelText.content = `  Active model: ${s.model || "unknown"}`;
      this.tunnelText.content = tunnelOk
        ? `  ${s.tunnel?.url}`
        : "  No tunnel active. Use Setup > Start Tunnel.";
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.statusText.content = `\x1b[31m  Error: ${msg}\x1b[0m`;
    }
  }
}
