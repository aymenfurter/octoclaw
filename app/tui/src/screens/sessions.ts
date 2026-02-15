/**
 * Sessions screen -- browse recorded chat sessions.
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
import { formatSessionTime, formatDuration, formatSize } from "../utils/format.js";

export class SessionsScreen extends Screen {
  private statsText!: TextRenderable;
  private policyText!: TextRenderable;
  private sessionSelect!: SelectRenderable;
  private detailText!: TextRenderable;
  private messagesScroll!: ScrollBoxRenderable;

  private sessions: Record<string, unknown>[] = [];

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    this.statsText = this.text("Loading...");
    this.container.add(this.statsText);

    this.policyText = this.text("");
    this.container.add(this.policyText);

    const listBox = this.section(" Sessions ", 15);
    this.sessionSelect = new SelectRenderable(this.renderer, {
      options: [{ name: "Loading...", description: "" }],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      flexGrow: 1,
    });
    listBox.add(this.sessionSelect);
    this.container.add(listBox);

    this.sessionSelect.on("itemSelected", () => {
      this.openSession(this.sessionSelect.getSelectedIndex());
    });

    const detailBox = this.section(" Session Detail ");
    this.detailText = this.text("Select a session from the list above.");
    detailBox.add(this.detailText);

    this.messagesScroll = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.surface,
      flexGrow: 1,
      width: "100%",
      flexDirection: "column",
    });
    detailBox.add(this.messagesScroll);
    this.container.add(detailBox);
  }

  refresh(): void {
    this.loadSessions();
    this.loadStats();
    this.loadPolicy();
  }

  // -----------------------------------------------------------------------
  // Factory helpers
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
  // Data loading
  // -----------------------------------------------------------------------

  private async loadStats(): Promise<void> {
    try {
      const stats = await this.api.getSessionStats();
      this.statsText.content = `  Sessions: ${stats.total_sessions ?? 0}  |  Messages: ${stats.total_messages ?? 0}  |  Storage: ${formatSize((stats.total_size_bytes as number) ?? 0)}`;
    } catch {
      this.statsText.content = "  Stats unavailable";
    }
  }

  private async loadPolicy(): Promise<void> {
    try {
      const p = await this.api.getSessionPolicy();
      const labels: Record<string, string> = { never: "Keep forever", "24h": "24 hours", "7d": "7 days", "30d": "30 days" };
      this.policyText.content = `  Archival policy: ${labels[p.policy] || p.policy}`;
    } catch {
      this.policyText.content = "";
    }
  }

  private async loadSessions(): Promise<void> {
    try {
      this.sessions = await this.api.listSessions() as Record<string, unknown>[];
      if (this.sessions.length === 0) {
        this.sessionSelect.options = [{ name: "(No sessions recorded)", description: "" }];
        return;
      }
      const opts: SelectOption[] = this.sessions.map((s) => {
        const time = formatSessionTime(s.started_at as string);
        const status = s.ended_at ? "" : " [active]";
        const preview = ((s.first_message as string) || "(empty)").slice(0, 50);
        return { name: `${time}${status}  ${s.message_count}msg  ${s.model || "?"}  ${preview}`, description: "" };
      });
      this.sessionSelect.options = opts;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.sessionSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private async openSession(index: number): Promise<void> {
    if (index < 0 || index >= this.sessions.length) return;
    const s = this.sessions[index];

    try {
      const session = await this.api.getSession(s.id as string) as Record<string, unknown>;
      if (!session || session.status === "error") {
        this.detailText.content = `\x1b[31m${(session?.message as string) || "Session not found"}\x1b[0m`;
        return;
      }

      // Clear old messages
      for (const child of this.messagesScroll.getChildren()) {
        this.messagesScroll.remove(child.id);
      }

      const started = formatSessionTime(session.started_at as string);
      const ended = session.ended_at ? formatSessionTime(session.ended_at as string) : "active";
      const dur = session.ended_at ? formatDuration(session.started_at as string, session.ended_at as string) : "";
      this.detailText.content = `  ${session.model || "?"}  |  ${session.channel || "web"}  |  ${started} -> ${ended}  ${dur ? "(" + dur + ")" : ""}  |  ${session.message_count} messages`;

      // Build timeline
      const timeline: { kind: string; ts: string; data: Record<string, unknown> }[] = [];
      for (const msg of (session.messages as Record<string, unknown>[]) || []) {
        timeline.push({ kind: "message", ts: msg.timestamp as string, data: msg });
      }
      for (const tc of (session.tool_calls as Record<string, unknown>[]) || []) {
        timeline.push({ kind: "tool", ts: tc.timestamp as string, data: tc });
      }
      timeline.sort((a, b) => (a.ts || "").localeCompare(b.ts || ""));

      let toolGroup: Record<string, unknown>[] = [];
      const flushTools = () => {
        if (toolGroup.length === 0) return;
        const names = toolGroup.map((t) => this.humanizeTool(t.tool as string)).join(", ");
        this.messagesScroll.add(new TextRenderable(this.renderer, {
          content: `  \x1b[90m[${toolGroup.length} tool${toolGroup.length > 1 ? "s" : ""}: ${names}]\x1b[0m`,
          fg: Colors.muted,
          width: "100%",
        }));
        toolGroup = [];
      };

      for (const entry of timeline) {
        if (entry.kind === "tool") {
          toolGroup.push(entry.data);
        } else {
          flushTools();
          const msg = entry.data;
          const roleColor = msg.role === "user" ? "\x1b[36m" : msg.role === "assistant" ? "\x1b[32m" : "\x1b[90m";
          const label = msg.role === "user" ? "You" : msg.role === "system" ? "System" : "Assistant";
          const time = formatSessionTime(msg.timestamp as string);

          this.messagesScroll.add(new TextRenderable(this.renderer, {
            content: `${roleColor}${label}\x1b[0m \x1b[90m${time}\x1b[0m\n${msg.text}`,
            fg: Colors.text,
            width: "100%",
            marginBottom: 1,
          }));
        }
      }
      flushTools();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.detailText.content = `\x1b[31mError: ${msg}\x1b[0m`;
    }
  }

  private humanizeTool(name: string): string {
    if (!name || name === "unknown") return "working";
    const segments = name.split("__");
    const clean = segments.length > 1 ? segments[segments.length - 1] : name;
    return clean.replace(/_/g, " ").replace(/-/g, " ");
  }
}
