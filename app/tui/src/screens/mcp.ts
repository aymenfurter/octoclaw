/**
 * MCP screen -- manage MCP servers and browse GitHub registry.
 */

import {
  BoxRenderable,
  TextRenderable,
  SelectRenderable,
  InputRenderable,
  ScrollBoxRenderable,
  type SelectOption,
} from "@opentui/core";
import { Screen } from "./screen.js";
import { Colors } from "../utils/theme.js";

interface McpServer {
  name: string;
  type: string;
  description?: string;
  enabled: boolean;
  command?: string;
  args?: string[];
  url?: string;
  tools?: { name: string }[];
}

interface RegistryEntry {
  name: string;
  stars: number;
  description?: string;
}

export class McpScreen extends Screen {
  capturesInput = true;

  private serverSelect!: SelectRenderable;
  private detailText!: TextRenderable;
  private resultText!: TextRenderable;
  private registrySelect!: SelectRenderable;
  private searchInput!: InputRenderable;
  private actionSelect!: SelectRenderable;

  // Add-form inputs
  private nameInput!: InputRenderable;
  private typeInput!: InputRenderable;
  private cmdInput!: InputRenderable;
  private urlInput!: InputRenderable;
  private descInput!: InputRenderable;

  private servers: McpServer[] = [];
  private registryServers: RegistryEntry[] = [];

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Configured servers list
    const serversBox = this.section(" MCP Servers ", 10);
    this.serverSelect = this.createSelect();
    serversBox.add(this.serverSelect);
    this.container.add(serversBox);

    this.serverSelect.on("selectionChanged", () => {
      this.showServerDetail(this.serverSelect.getSelectedIndex());
    });

    // Actions
    const actionsBox = this.section(" Actions ", 5);
    this.actionSelect = new SelectRenderable(this.renderer, {
      options: [
        { name: "Enable Selected", description: "" },
        { name: "Disable Selected", description: "" },
        { name: "Remove Selected", description: "" },
        { name: "Add New Server", description: "" },
      ],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
    });
    actionsBox.add(this.actionSelect);
    this.container.add(actionsBox);

    this.actionSelect.on("itemSelected", () => {
      this.handleAction(this.actionSelect.getSelectedIndex());
    });

    // Add server form
    const formBox = this.section(" Add MCP Server ");
    this.nameInput = this.addFormField(formBox, "Name:", "my-mcp-server");
    this.typeInput = this.addFormField(formBox, "Type (local/http/sse):", "local");
    this.cmdInput = this.addFormField(formBox, "Command (for local):", "npx -y @some/mcp-server");
    this.urlInput = this.addFormField(formBox, "URL (for http/sse):", "https://...");
    this.descInput = this.addFormField(formBox, "Description:", "What this server does");
    this.container.add(formBox);

    // Detail
    this.detailText = this.text("");
    this.container.add(this.detailText);

    // GitHub Registry browser
    const regBox = this.section(" GitHub MCP Registry ", 10);
    this.searchInput = this.input("Search registry (Ctrl+Enter to search)...");
    regBox.add(this.searchInput);
    this.registrySelect = new SelectRenderable(this.renderer, {
      options: [{ name: "(Press Ctrl+Enter in search to load registry)", description: "" }],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      flexGrow: 1,
    });
    regBox.add(this.registrySelect);
    this.container.add(regBox);

    // Result
    this.resultText = this.text("");
    this.container.add(this.resultText);

    // Ctrl+Enter to search registry
    this.renderer.keyInput.on("keypress", (key: { name: string; ctrl?: boolean }) => {
      if (!this.isVisible()) return;
      if (key.name === "return" && key.ctrl) this.searchRegistry();
    });
  }

  refresh(): void {
    this.loadServers();
  }

  // -----------------------------------------------------------------------
  // Factory helpers
  // -----------------------------------------------------------------------

  private text(content: string): TextRenderable {
    return new TextRenderable(this.renderer, { content, fg: Colors.muted, width: "100%" });
  }

  private input(placeholder: string): InputRenderable {
    return new InputRenderable(this.renderer, { placeholder, textColor: Colors.text, width: "100%" });
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
      rowGap: 1,
    });
  }

  /** Add a label + input pair to a container and return the input. */
  private addFormField(parent: BoxRenderable, label: string, placeholder: string): InputRenderable {
    parent.add(new TextRenderable(this.renderer, {
      content: label,
      fg: Colors.muted,
      width: "100%",
      height: 1,
    }));
    const inp = this.input(placeholder);
    parent.add(inp);
    return inp;
  }

  // -----------------------------------------------------------------------
  // Data
  // -----------------------------------------------------------------------

  private async loadServers(): Promise<void> {
    try {
      const r = (await this.api.listMcpServers()) as { servers?: McpServer[] };
      this.servers = r.servers || [];
      if (this.servers.length === 0) {
        this.serverSelect.options = [{ name: "(No MCP servers configured)", description: "" }];
        return;
      }
      const opts: SelectOption[] = this.servers.map((s) => {
        const status = s.enabled ? "[on]" : "[off]";
        return { name: `${status} ${s.name}  ${s.type}  ${s.description || ""}`, description: "" };
      });
      this.serverSelect.options = opts;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.serverSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private showServerDetail(index: number): void {
    if (index < 0 || index >= this.servers.length) return;
    const s = this.servers[index];
    const lines = [
      `  ${s.name}`,
      `  ${s.description || ""}`,
      "",
      `  Type:    ${s.type}`,
      `  Enabled: ${s.enabled ? "Yes" : "No"}`,
    ];
    if (s.command) lines.push(`  Command: ${s.command} ${(s.args || []).join(" ")}`);
    if (s.url) lines.push(`  URL:     ${s.url}`);
    if (s.tools?.length) lines.push(`  Tools:   ${s.tools.map((t) => t.name).join(", ")}`);
    this.detailText.content = lines.join("\n");
  }

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  private async handleAction(index: number): Promise<void> {
    const dispatch: (() => Promise<void>)[] = [
      () => this.toggleServer(true),
      () => this.toggleServer(false),
      () => this.removeSelected(),
      () => this.addServer(),
    ];
    if (dispatch[index]) await dispatch[index]();
  }

  private getSelected(): McpServer | null {
    const i = this.serverSelect.getSelectedIndex();
    return i >= 0 && i < this.servers.length ? this.servers[i] : null;
  }

  private async toggleServer(enable: boolean): Promise<void> {
    const s = this.getSelected();
    if (!s) return;
    try {
      if (enable) await this.api.enableMcpServer(s.name);
      else await this.api.disableMcpServer(s.name);
      this.resultText.content = `  \x1b[32m${enable ? "Enabled" : "Disabled"} ${s.name}\x1b[0m`;
      this.loadServers();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async removeSelected(): Promise<void> {
    const s = this.getSelected();
    if (!s) return;
    try {
      await this.api.removeMcpServer(s.name);
      this.resultText.content = `  \x1b[32mRemoved ${s.name}\x1b[0m`;
      this.loadServers();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async addServer(): Promise<void> {
    const name = this.nameInput.value?.trim();
    const type = this.typeInput.value?.trim();
    if (!name || !type) {
      this.resultText.content = "  \x1b[31mName and type are required\x1b[0m";
      return;
    }
    try {
      await this.api.addMcpServer({
        name,
        type,
        command: this.cmdInput.value?.trim() || "",
        url: this.urlInput.value?.trim() || "",
        description: this.descInput.value?.trim() || "",
        enabled: true,
      });
      this.resultText.content = `  \x1b[32mAdded ${name}\x1b[0m`;
      for (const inp of [this.nameInput, this.typeInput, this.cmdInput, this.urlInput, this.descInput]) {
        inp.value = "";
      }
      this.loadServers();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async searchRegistry(): Promise<void> {
    const query = this.searchInput.value?.trim() || "";
    this.resultText.content = "  Searching registry...";
    try {
      const r = (await this.api.getMcpRegistry(1, query)) as { servers?: RegistryEntry[] };
      this.registryServers = r.servers || [];
      if (this.registryServers.length === 0) {
        this.registrySelect.options = [{ name: "(No results)", description: "" }];
      } else {
        const opts: SelectOption[] = this.registryServers.map((s) => ({
          name: `${s.name}  ★${s.stars}  ${(s.description || "").slice(0, 40)}`,
          description: "",
        }));
        this.registrySelect.options = opts;
      }
      this.resultText.content = `  Found ${this.registryServers.length} servers`;
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }
}
