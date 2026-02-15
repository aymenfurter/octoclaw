/**
 * Profile screen -- view and edit agent profile.
 */

import {
  BoxRenderable,
  TextRenderable,
  InputRenderable,
  SelectRenderable,
  ScrollBoxRenderable,
} from "@opentui/core";
import { Screen } from "./screen.js";
import { Colors } from "../utils/theme.js";

interface AgentProfile {
  name?: string;
  location?: string;
  emotional_state?: string;
  identity?: string;
  preferences?: Record<string, unknown>;
  memory_summary?: string;
}

export class ProfileScreen extends Screen {
  capturesInput = true;

  private profileText!: TextRenderable;
  private nameInput!: InputRenderable;
  private locationInput!: InputRenderable;
  private emotionalInput!: InputRenderable;
  private resultText!: TextRenderable;
  private actionSelect!: SelectRenderable;

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Current profile display
    const profileBox = this.section(" Agent Profile ");
    this.profileText = this.text("Loading...");
    profileBox.add(this.profileText);
    this.container.add(profileBox);

    // Edit form
    const formBox = this.section(" Edit Profile ");
    this.nameInput = this.addFormField(formBox, "Name:", "Agent name");
    this.locationInput = this.addFormField(formBox, "Location:", "Agent location");
    this.emotionalInput = this.addFormField(formBox, "Emotional State:", "e.g. curious, focused");
    this.container.add(formBox);

    // Actions
    this.actionSelect = new SelectRenderable(this.renderer, {
      options: [
        { name: "Save Profile", description: "" },
        { name: "Refresh", description: "" },
      ],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      height: 3,
    });
    this.container.add(this.actionSelect);

    this.actionSelect.on("itemSelected", () => {
      const i = this.actionSelect.getSelectedIndex();
      if (i === 0) this.saveProfile();
      else this.refresh();
    });

    // Result
    this.resultText = this.text("");
    this.container.add(this.resultText);
  }

  refresh(): void {
    this.loadProfile();
  }

  // -----------------------------------------------------------------------
  // Helpers
  // -----------------------------------------------------------------------

  private text(content: string): TextRenderable {
    return new TextRenderable(this.renderer, { content, fg: Colors.muted, width: "100%" });
  }

  private input(placeholder: string): InputRenderable {
    return new InputRenderable(this.renderer, { placeholder, textColor: Colors.text, width: "100%" });
  }

  private section(title: string): BoxRenderable {
    return new BoxRenderable(this.renderer, {
      border: true,
      borderColor: Colors.border,
      title,
      backgroundColor: Colors.surface,
      width: "100%",
      flexGrow: 1,
      padding: 1,
      flexDirection: "column",
      rowGap: 1,
    });
  }

  private addFormField(parent: BoxRenderable, label: string, placeholder: string): InputRenderable {
    parent.add(new TextRenderable(this.renderer, { content: label, fg: Colors.muted, width: "100%", height: 1 }));
    const inp = this.input(placeholder);
    parent.add(inp);
    return inp;
  }

  // -----------------------------------------------------------------------
  // Data
  // -----------------------------------------------------------------------

  private async loadProfile(): Promise<void> {
    try {
      const p = (await this.api.getProfile()) as AgentProfile;
      const lines = [
        `  Name:            ${p.name || "(not set)"}`,
        `  Location:        ${p.location || "(not set)"}`,
        `  Emotional State: ${p.emotional_state || "(not set)"}`,
        `  Identity:        ${p.identity || ""}`,
      ];
      if (p.preferences) {
        lines.push("", "  Preferences:");
        for (const [k, v] of Object.entries(p.preferences)) {
          lines.push(`    ${k}: ${v}`);
        }
      }
      if (p.memory_summary) {
        lines.push("", "  Memory:", `    ${p.memory_summary}`);
      }
      this.profileText.content = lines.join("\n");

      // Pre-fill form
      this.nameInput.value = p.name || "";
      this.locationInput.value = p.location || "";
      this.emotionalInput.value = p.emotional_state || "";
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.profileText.content = `\x1b[31mError: ${msg}\x1b[0m`;
    }
  }

  private async saveProfile(): Promise<void> {
    const data: Record<string, string> = {};
    const name = this.nameInput.value?.trim();
    const location = this.locationInput.value?.trim();
    const emotional = this.emotionalInput.value?.trim();
    if (name) data.name = name;
    if (location) data.location = location;
    if (emotional) data.emotional_state = emotional;

    try {
      const r = await this.api.updateProfile(data);
      this.resultText.content = `  \x1b[32m${r.message || "Profile updated"}\x1b[0m`;
      this.loadProfile();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }
}
