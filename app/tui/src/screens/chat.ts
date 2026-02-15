/**
 * Chat screen -- placeholder for the tab-based TUI.
 *
 * The full WebSocket-based chat experience is implemented in the
 * original-style TUI (see ui/app.ts). This screen provides a
 * simplified chat view for the component-based tab layout.
 */

import {
  BoxRenderable,
  TextRenderable,
  InputRenderable,
  InputRenderableEvents,
  ScrollBoxRenderable,
} from "@opentui/core";
import { Screen } from "./screen.js";
import { Colors } from "../utils/theme.js";

export class ChatScreen extends Screen {
  capturesInput = true;

  private chatScroll!: ScrollBoxRenderable;
  private chatInput!: InputRenderable;
  private ws: WebSocket | null = null;
  private msgCounter = 0;

  async build(): Promise<void> {
    this.container = new BoxRenderable(this.renderer, {
      backgroundColor: Colors.bg,
      flexDirection: "column",
      width: "100%",
      flexGrow: 1,
    });

    this.chatScroll = new ScrollBoxRenderable(this.renderer, {
      backgroundColor: Colors.surface,
      flexGrow: 1,
      width: "100%",
      stickyScroll: true,
      stickyStart: "bottom",
      border: true,
      borderColor: Colors.border,
      title: " Chat ",
      contentOptions: { paddingLeft: 1, paddingRight: 1 },
    });
    this.container.add(this.chatScroll);

    const inputBox = new BoxRenderable(this.renderer, {
      height: 3,
      border: true,
      borderColor: Colors.accent,
      paddingLeft: 1,
      paddingRight: 1,
    });

    this.chatInput = new InputRenderable(this.renderer, {
      width: "100%",
      placeholder: "Type a message...",
      focusedBackgroundColor: Colors.surface,
      textColor: Colors.text,
      cursorColor: Colors.accent,
    });
    inputBox.add(this.chatInput);
    this.container.add(inputBox);

    this.chatInput.on(InputRenderableEvents.CHANGE, (value: unknown) => {
      const text = String(value ?? "").trim();
      if (!text) return;
      this.sendMessage(text);
      try { this.chatInput.value = ""; } catch { /* ignore */ }
    });
  }

  refresh(): void {
    this.ensureWebSocket();
  }

  private addLine(text: string, color: string): void {
    const id = `chat-msg-${++this.msgCounter}`;
    const msg = new TextRenderable(this.renderer, { id, content: text, fg: color });
    this.chatScroll.add(msg);

    // Keep bounded
    const children = this.chatScroll.getChildren();
    while (children.length > 500) {
      const oldest = children.shift();
      if (oldest) {
        this.chatScroll.remove(oldest.id);
        oldest.destroyRecursively();
      }
    }
  }

  private sendMessage(text: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      this.addLine("[system]: Not connected", Colors.yellow);
      return;
    }
    this.ws.send(JSON.stringify({ action: "send", message: text }));
    this.addLine(`You: ${text}`, Colors.green);
  }

  private ensureWebSocket(): void {
    if (this.ws && this.ws.readyState <= WebSocket.OPEN) return;
    try {
      const baseUrl = (this.api as unknown as { baseUrl: string }).baseUrl || "";
      const wsBase = baseUrl.replace(/^https:/, "wss:").replace(/^http:/, "ws:");
      const secret = (this.api as unknown as { secret: string }).secret || "";
      const wsUrl = secret ? `${wsBase}/api/chat/ws?token=${secret}` : `${wsBase}/api/chat/ws`;

      this.ws = new WebSocket(wsUrl);
      this.ws.onopen = () => this.addLine("[system]: Connected", Colors.muted);
      this.ws.onmessage = (ev) => {
        try {
          const data = JSON.parse(String(ev.data));
          if (data.type === "delta" && data.content) {
            this.addLine(`Bot: ${data.content}`, Colors.accent);
          } else if (data.type === "message") {
            this.addLine(`Bot: ${data.content || "(no response)"}`, Colors.accent);
          } else if (data.type === "error") {
            this.addLine(`[error]: ${data.content}`, Colors.red);
          }
        } catch { /* ignore */ }
      };
      this.ws.onclose = () => {
        this.addLine("[system]: Disconnected", Colors.muted);
        setTimeout(() => this.ensureWebSocket(), 3000);
      };
    } catch { /* ignore */ }
  }
}
