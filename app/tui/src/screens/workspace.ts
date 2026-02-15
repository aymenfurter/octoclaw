/**
 * Workspace screen -- file browser for the data directory.
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
import { formatSize } from "../utils/format.js";

interface DirEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size?: number;
}

export class WorkspaceScreen extends Screen {
  private pathText!: TextRenderable;
  private fileSelect!: SelectRenderable;
  private previewText!: TextRenderable;

  private entries: DirEntry[] = [];
  private currentPath = "data";

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Current path
    this.pathText = new TextRenderable(this.renderer, {
      content: "  data/",
      fg: Colors.accent,
      width: "100%",
      height: 1,
    });
    this.container.add(this.pathText);

    // File list
    const listBox = this.section(" Files ", 15);
    this.fileSelect = new SelectRenderable(this.renderer, {
      options: [{ name: "Loading...", description: "" }],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      flexGrow: 1,
    });
    listBox.add(this.fileSelect);
    this.container.add(listBox);

    this.fileSelect.on("itemSelected", () => {
      this.handleSelect(this.fileSelect.getSelectedIndex());
    });

    // File preview
    const previewBox = this.section(" Preview ");
    const previewScroll = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.surface,
      flexGrow: 1,
      width: "100%",
      flexDirection: "column",
    });
    this.previewText = new TextRenderable(this.renderer, {
      content: "  Select a file to preview.",
      fg: Colors.muted,
      width: "100%",
    });
    previewScroll.add(this.previewText);
    previewBox.add(previewScroll);
    this.container.add(previewBox);

    // Backspace to go up
    this.renderer.keyInput.on("keypress", (key: { name: string }) => {
      if (!this.isVisible()) return;
      if (key.name === "backspace") this.goUp();
    });
  }

  refresh(): void {
    this.loadDir();
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

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
  // Navigation
  // -----------------------------------------------------------------------

  private async loadDir(): Promise<void> {
    this.pathText.content = `  ${this.currentPath}/`;
    try {
      const r = (await this.api.listWorkspaceDir(this.currentPath)) as { entries?: DirEntry[] };
      this.entries = r.entries || [];

      const opts: SelectOption[] = [];
      if (this.currentPath !== "data") {
        opts.push({ name: ".. (parent directory)", description: "" });
      }
      for (const e of this.entries) {
        if (e.is_dir) {
          opts.push({ name: `${e.name}/`, description: "directory" });
        } else {
          const size = e.size !== undefined ? `  ${formatSize(e.size)}` : "";
          opts.push({ name: `${e.name}${size}`, description: "" });
        }
      }

      this.fileSelect.options = opts.length > 0 ? opts : [{ name: "(Empty directory)", description: "" }];
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.fileSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private handleSelect(index: number): void {
    let adjustedIndex = index;
    if (this.currentPath !== "data") {
      if (index === 0) {
        this.goUp();
        return;
      }
      adjustedIndex = index - 1;
    }

    if (adjustedIndex < 0 || adjustedIndex >= this.entries.length) return;
    const entry = this.entries[adjustedIndex];

    if (entry.is_dir) {
      this.currentPath = entry.path;
      this.loadDir();
    } else {
      this.loadFile(entry.path);
    }
  }

  private goUp(): void {
    if (this.currentPath === "data") return;
    const parts = this.currentPath.split("/");
    parts.pop();
    this.currentPath = parts.join("/") || "data";
    this.loadDir();
  }

  private async loadFile(path: string): Promise<void> {
    try {
      const r = (await this.api.readWorkspaceFile(path)) as {
        binary?: boolean;
        size?: number;
        content?: string;
        truncated?: boolean;
      };
      if (r.binary) {
        this.previewText.content = `  (Binary file, ${formatSize(r.size ?? 0)})`;
      } else {
        const content = r.content || "(empty)";
        const truncNote = r.truncated ? "\n... (truncated)" : "";
        this.previewText.content = content + truncNote;
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.previewText.content = `\x1b[31mError: ${msg}\x1b[0m`;
    }
  }
}
