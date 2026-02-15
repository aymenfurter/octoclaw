/**
 * Skills screen -- list installed skills with descriptions.
 *
 * The original codebase referenced a SkillsScreen but never shipped an
 * implementation. This screen provides a read-only view of the skills
 * registered via the `/skills` slash command, fetching data from the
 * `/api/plugins` endpoint (skills are nested under plugins).
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

interface Skill {
  name: string;
  description?: string;
  plugin?: string;
}

export class SkillsScreen extends Screen {
  private skillSelect!: SelectRenderable;
  private detailText!: TextRenderable;

  private skills: Skill[] = [];

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Skill list
    const listBox = this.section(" Skills ", 15);
    this.skillSelect = new SelectRenderable(this.renderer, {
      options: [{ name: "Loading...", description: "" }],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      flexGrow: 1,
    });
    listBox.add(this.skillSelect);
    this.container.add(listBox);

    this.skillSelect.on("selectionChanged", () => {
      this.showDetail(this.skillSelect.getSelectedIndex());
    });

    // Detail panel
    const detailBox = this.section(" Skill Detail ");
    this.detailText = this.text("  Select a skill to view details.");
    detailBox.add(this.detailText);
    this.container.add(detailBox);
  }

  refresh(): void {
    this.loadSkills();
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  private text(content: string): TextRenderable {
    return new TextRenderable(this.renderer, { content, fg: Colors.muted, width: "100%" });
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

  private async loadSkills(): Promise<void> {
    try {
      const r = (await this.api.listPlugins()) as {
        plugins?: { name: string; skills?: { name: string; description?: string }[] }[];
      };
      const plugins = r.plugins || [];
      this.skills = [];
      for (const p of plugins) {
        for (const s of p.skills || []) {
          this.skills.push({ name: s.name, description: s.description, plugin: p.name });
        }
      }

      if (this.skills.length === 0) {
        this.skillSelect.options = [{ name: "(No skills installed)", description: "" }];
        return;
      }

      const opts: SelectOption[] = this.skills.map((s) => ({
        name: `${s.name}  ${s.description || ""}`,
        description: "",
      }));
      this.skillSelect.options = opts;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.skillSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private showDetail(index: number): void {
    if (index < 0 || index >= this.skills.length) return;
    const s = this.skills[index];
    this.detailText.content = [
      `  ${s.name}`,
      `  ${s.description || ""}`,
      "",
      `  Plugin:  ${s.plugin || "(unknown)"}`,
    ].join("\n");
  }
}
