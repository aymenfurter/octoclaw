"""Interactive CLI -- alternative to the web admin interface."""

from __future__ import annotations

import asyncio

from prompt_toolkit import PromptSession
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import FileHistory
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown

from .agent.agent import Agent
from .config.settings import cfg
from .scheduler import scheduler_loop

console = Console()

_COMMANDS = {"/quit", "/exit", "/new"}


async def _main() -> None:
    cfg.ensure_dirs()
    console.print("[bold green]octoclaw[/bold green] v4\nType [bold]/quit[/bold] to exit, [bold]/new[/bold] for a new session.\n")

    agent = Agent()
    await agent.start()
    sched_task = asyncio.create_task(scheduler_loop())

    history_path = cfg.data_dir / ".cli_history"
    prompt_session: PromptSession[str] = PromptSession(history=FileHistory(str(history_path)))

    try:
        while True:
            try:
                user_input = await asyncio.to_thread(prompt_session.prompt, HTML("<b>you &gt;</b> "))
            except (EOFError, KeyboardInterrupt):
                break

            text = user_input.strip()
            if not text:
                continue
            if text.lower() in ("/quit", "/exit"):
                break
            if text.lower() == "/new":
                await agent.new_session()
                console.print("[dim]-- new session --[/dim]")
                continue

            console.print()
            chunks: list[str] = []

            with Live(Markdown("..."), console=console, refresh_per_second=8) as live:

                def on_delta(delta: str) -> None:
                    chunks.append(delta)
                    live.update(Markdown("".join(chunks)))

                response = await agent.send(text, on_delta=on_delta)

            if not chunks and response:
                console.print(Markdown(response))

            console.print()
    finally:
        sched_task.cancel()
        await agent.stop()
        console.print("[dim]Goodbye.[/dim]")


def main() -> None:
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
