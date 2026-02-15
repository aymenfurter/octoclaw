/**
 * Plugins screen -- list, enable/disable, and remove plugins.
 */

import {
  BoxRenderable,
  TextRenderable,
  SelectRenderable,
  ScrollBoxRenderable,
  type SelectOption,
} from "@opentui/core";
import { Screen } from "./screen.js";
import { Colors } from "../utils/theme.js";

interface Plugin {
  id: string;
  name: string;
  description?: string;
  enabled: boolean;
  bundled: boolean;
  needs_setup: boolean;
  skills?: { name: string }[];
}

export class PluginsScreen extends Screen {
  private pluginSelect!: SelectRenderable;
  private detailText!: TextRenderable;
  private resultText!: TextRenderable;

  private plugins: Plugin[] = [];

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Plugin list
    const listBox = this.section(" Plugins ", 12);
    this.pluginSelect = this.createSelect();
    listBox.add(this.pluginSelect);
    this.container.add(listBox);

    this.pluginSelect.on("selectionChanged", () => {
      this.showDetail(this.pluginSelect.getSelectedIndex());
    });

    // Detail panel
    const detailBox = this.section(" Plugin Detail ");
    this.detailText = this.text(
      "  Select a plugin to view details.\n\n  \x1b[90mPress 'e' to enable, 'd' to disable, 'x' to remove\x1b[0m",
    );
    detailBox.add(this.detailText);
    this.container.add(detailBox);

    // Result line
    this.resultText = this.text("");
    this.container.add(this.resultText);

    // Key bindings
    this.renderer.keyInput.on("keypress", (key: { name: string }) => {
      if (!this.isVisible()) return;
      if (key.name === "e") this.enableSelected();
      else if (key.name === "d") this.disableSelected();
      else if (key.name === "x") this.removeSelected();
    });
  }

  refresh(): void {
    this.loadPlugins();
  }

  // -----------------------------------------------------------------------
  // Factory helpers
  // -----------------------------------------------------------------------

  private text(content: string): TextRenderable {
    return new TextRenderable(this.renderer, { content, fg: Colors.muted, width: "100%" });
  }

  private createSelect(): SelectRenderable {
    return new SelectRenderable(this.renderer, {
      options: [{ name: "Loading...", description: "" }],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      flexGrow: 1,
    });
  }

  private section(title: string, height?: number): BoxRenderable {
    return new BoxRenderable(this.renderer, {
      border: true,
      borderColor: Colors.border,
      title,
      backgroundColor: Colors.surface,
      width: "100%",
      ...(height ? { height } : { flexGrow: 1 }),
      padding: 1,
      flexDirection: "column",
    });
  }

  // -----------------------------------------------------------------------
  // Data
  // -----------------------------------------------------------------------

  private async loadPlugins(): Promise<void> {
    try {
      const r = (await this.api.listPlugins()) as { plugins?: Plugin[] };
      this.plugins = r.plugins || [];
      if (this.plugins.length === 0) {
        this.pluginSelect.options = [{ name: "(No plugins installed)", description: "" }];
        return;
      }
      const opts: SelectOption[] = this.plugins.map((p) => {
        const status = p.enabled ? "[on]" : "[off]";
        const setup = p.needs_setup ? " [needs setup]" : "";
        return { name: `${status} ${p.name}${setup}  ${p.description || ""}`, description: "" };
      });
      this.pluginSelect.options = opts;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.pluginSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private showDetail(index: number): void {
    if (index < 0 || index >= this.plugins.length) return;
    const p = this.plugins[index];
    const lines = [
      `  ${p.name}`,
      `  ${p.description || ""}`,
      "",
      `  ID:       ${p.id}`,
      `  Enabled:  ${p.enabled ? "Yes" : "No"}`,
      `  Bundled:  ${p.bundled ? "Yes" : "No"}`,
      `  Setup:    ${p.needs_setup ? "Needs setup" : "Complete"}`,
    ];
    if (p.skills?.length) {
      lines.push(`  Skills:   ${p.skills.map((s) => s.name).join(", ")}`);
    }
    lines.push("", "  \x1b[90mPress 'e' to enable, 'd' to disable, 'x' to remove\x1b[0m");
    this.detailText.content = lines.join("\n");
  }

  private getSelectedPlugin(): Plugin | null {
    const index = this.pluginSelect.getSelectedIndex();
    return index >= 0 && index < this.plugins.length ? this.plugins[index] : null;
  }

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  private async enableSelected(): Promise<void> {
    const p = this.getSelectedPlugin();
    if (!p) return;
    try {
      const r = await this.api.enablePlugin(p.id);
      this.resultText.content = `  \x1b[32m${r.message || "Enabled"}\x1b[0m`;
      this.loadPlugins();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async disableSelected(): Promise<void> {
    const p = this.getSelectedPlugin();
    if (!p) return;
    try {
      const r = await this.api.disablePlugin(p.id);
      this.resultText.content = `  \x1b[32m${r.message || "Disabled"}\x1b[0m`;
      this.loadPlugins();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async removeSelected(): Promise<void> {
    const p = this.getSelectedPlugin();
    if (!p) return;
    try {
      const r = await this.api.removePlugin(p.id);
      this.resultText.content = `  \x1b[32m${r.message || "Removed"}\x1b[0m`;
      this.loadPlugins();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }
}
