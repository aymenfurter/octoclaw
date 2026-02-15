/**
 * Scheduler screen -- CRUD for scheduled tasks.
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

interface ScheduledTask {
  id: string;
  description?: string;
  prompt?: string;
  cron?: string;
  run_at?: string;
  last_run?: string;
  next_run?: string;
  created_at?: string;
}

export class SchedulerScreen extends Screen {
  capturesInput = true;

  private taskSelect!: SelectRenderable;
  private detailText!: TextRenderable;
  private resultText!: TextRenderable;
  private actionSelect!: SelectRenderable;

  // Create form
  private descInput!: InputRenderable;
  private promptInput!: InputRenderable;
  private cronInput!: InputRenderable;
  private runAtInput!: InputRenderable;

  private tasks: ScheduledTask[] = [];

  async build(): Promise<void> {
    this.container = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
      rowGap: 1,
      padding: 1,
    });

    // Task list
    const listBox = this.section(" Scheduled Tasks ", 10);
    this.taskSelect = this.createSelect();
    listBox.add(this.taskSelect);
    this.container.add(listBox);

    this.taskSelect.on("selectionChanged", () => {
      this.showTaskDetail(this.taskSelect.getSelectedIndex());
    });

    // Actions
    this.actionSelect = new SelectRenderable(this.renderer, {
      options: [
        { name: "Create New Task", description: "" },
        { name: "Delete Selected Task", description: "" },
      ],
      textColor: Colors.text,
      selectedTextColor: Colors.accent,
      width: "100%",
      height: 3,
    });
    this.container.add(this.actionSelect);

    this.actionSelect.on("itemSelected", () => {
      const i = this.actionSelect.getSelectedIndex();
      if (i === 0) this.createTask();
      else if (i === 1) this.deleteSelected();
    });

    // Create form
    const formBox = this.section(" New Task ");
    this.descInput = this.addFormField(formBox, "Description:", "What this task does");
    this.promptInput = this.addFormField(formBox, "Prompt:", "The prompt to send to the agent");
    this.cronInput = this.addFormField(formBox, "Cron expression (for recurring):", "0 9 * * * (daily at 9am)");
    this.runAtInput = this.addFormField(formBox, "Run at (ISO datetime, for one-time):", "2025-01-01T09:00:00");
    this.container.add(formBox);

    // Detail
    this.detailText = this.text("");
    this.container.add(this.detailText);

    // Result
    this.resultText = this.text("");
    this.container.add(this.resultText);
  }

  refresh(): void {
    this.loadTasks();
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

  private addFormField(parent: BoxRenderable, label: string, placeholder: string): InputRenderable {
    parent.add(new TextRenderable(this.renderer, { content: label, fg: Colors.muted, width: "100%", height: 1 }));
    const inp = this.input(placeholder);
    parent.add(inp);
    return inp;
  }

  // -----------------------------------------------------------------------
  // Data
  // -----------------------------------------------------------------------

  private async loadTasks(): Promise<void> {
    try {
      this.tasks = (await this.api.listSchedules()) as unknown as ScheduledTask[];
      if (this.tasks.length === 0) {
        this.taskSelect.options = [{ name: "(No scheduled tasks)", description: "" }];
        return;
      }
      const opts: SelectOption[] = this.tasks.map((t) => {
        const cron = t.cron ? `cron: ${t.cron}` : t.run_at ? `at: ${t.run_at}` : "no schedule";
        return { name: `${t.description || "(untitled)"}  ${cron}`, description: "" };
      });
      this.taskSelect.options = opts;
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : String(err);
      this.taskSelect.options = [{ name: `Error: ${msg}`, description: "" }];
    }
  }

  private showTaskDetail(index: number): void {
    if (index < 0 || index >= this.tasks.length) return;
    const t = this.tasks[index];
    this.detailText.content = [
      `  ${t.description || "(untitled)"}`,
      "",
      `  ID:          ${t.id}`,
      `  Prompt:      ${(t.prompt || "").slice(0, 60)}`,
      `  Cron:        ${t.cron || "(none)"}`,
      `  Run at:      ${t.run_at || "(none)"}`,
      `  Last run:    ${t.last_run || "(never)"}`,
      `  Next run:    ${t.next_run || "(unknown)"}`,
      `  Created:     ${t.created_at || ""}`,
    ].join("\n");
  }

  // -----------------------------------------------------------------------
  // Actions
  // -----------------------------------------------------------------------

  private async createTask(): Promise<void> {
    const prompt = this.promptInput.value?.trim();
    if (!prompt) {
      this.resultText.content = "  \x1b[31mPrompt is required\x1b[0m";
      return;
    }
    const body: Record<string, string> = {
      description: this.descInput.value?.trim() || "",
      prompt,
    };
    const cron = this.cronInput.value?.trim();
    const runAt = this.runAtInput.value?.trim();
    if (cron) body.cron = cron;
    if (runAt) body.run_at = runAt;

    try {
      await this.api.createSchedule(body);
      this.resultText.content = "  \x1b[32mTask created\x1b[0m";
      for (const inp of [this.descInput, this.promptInput, this.cronInput, this.runAtInput]) {
        inp.value = "";
      }
      this.loadTasks();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }

  private async deleteSelected(): Promise<void> {
    const index = this.taskSelect.getSelectedIndex();
    if (index < 0 || index >= this.tasks.length) return;
    try {
      await this.api.deleteSchedule(this.tasks[index].id);
      this.resultText.content = "  \x1b[32mTask deleted\x1b[0m";
      this.loadTasks();
    } catch (err: unknown) {
      this.resultText.content = `  \x1b[31m${err instanceof Error ? err.message : err}\x1b[0m`;
    }
  }
}
