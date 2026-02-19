# AGENTS.md -- Custom Instructions for Polyclaw

## Project Overview

Polyclaw is an autonomous AI copilot built on the GitHub Copilot SDK. It runs outside the IDE: browser, terminal, messaging apps, and phone calls. The codebase has three main surfaces: a Python backend (`app/runtime/`), a React + TypeScript frontend (`app/frontend/`), and a Node.js terminal UI (`app/tui/`).

## Repository Layout

```
app/runtime/          Python backend (aiohttp, Copilot SDK, Azure integrations)
app/frontend/         React 19 + TypeScript SPA (Vite, Playwright E2E)
app/tui/              Ink-based terminal UI (TypeScript)
plugins/              Plugin packs (PLUGIN.json + skill markdown files)
skills/               Built-in skill definitions (SKILL.md with YAML frontmatter)
docs/                 Hugo documentation site
scripts/              Shell helpers for local dev
```

## Python Backend (`app/runtime/`)

### Style and Tooling

- **Ruff** enforces style: line-length 100, target Python 3.11, rules `E`, `W`, `F`, `I` (isort), `UP` (pyupgrade).
- Every file starts with `from __future__ import annotations`.
- Use PEP 604 union syntax (`str | None`) instead of `Optional[str]`.
- Use `collections.abc` for abstract types (`Callable`, `Awaitable`), not `typing` equivalents.
- Annotate every function signature fully, including `-> None` on void functions.
- Use `%`-style formatting in log calls (lazy evaluation), never f-strings.

### Imports

1. `from __future__ import annotations`
2. Standard library
3. Third-party packages
4. Relative imports for intra-package references

Production code uses **relative imports** (`from ..config.settings import cfg`). Test code uses **absolute imports** (`from app.runtime.config.settings import Settings`).

### Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Modules | `snake_case` | `event_handler.py` |
| Private modules | Leading underscore | `_json_store.py` |
| Classes | `PascalCase` | `EventHandler`, `McpConfigStore` |
| Functions/methods | `snake_case` | `build_system_prompt()` |
| Private methods | Leading underscore | `_handle_delta()` |
| Constants | `UPPER_SNAKE_CASE` | `MAX_START_RETRIES` |
| Module-level private constants | `_UPPER_SNAKE_CASE` | `_BUILTIN_SERVERS` |

### Architecture Patterns

- **Configuration**: Singleton `cfg = Settings()` accessed via `from ..config.settings import cfg`. Reads from `.env` file and `os.getenv`, with `@kv:` prefix for Azure Key Vault resolution.
- **State stores**: JSON-file-backed, built on `_json_store.JsonStore` with `threading.Lock` for thread safety. One store class per concern (e.g., `McpConfigStore`, `SessionStore`).
- **Singletons**: Module-level `_instance: T | None = None` with `get_*()` factory and `_reset_*()` teardown registered via `register_singleton()` for test isolation.
- **Route handlers**: One class per feature area with a `register(router)` method. App wired in `AppFactory.build()`.
- **Error responses**: JSON envelope `{"status": "error", "message": "..."}` with appropriate HTTP codes.
- **Tools**: Defined with `@define_tool` decorator + `pydantic.BaseModel` for parameter schemas.
- **Event dispatch**: Dict-based dispatch table (`_DISPATCH_TABLE`) mapping event types to handler methods, not if/elif chains.
- **Async bridging**: Use `run_sync()` helper to run blocking code in an executor. Background loops via `asyncio.create_task()`.
- **Safe teardown**: Wrap cleanup in `_safe_*()` methods that catch all exceptions to prevent cascade failures.
- **`Result` type**: Frozen dataclass with `ok()`/`fail()` constructors and boolean evaluation for operations that can fail.
- **Immutable collections**: Use `frozenset` for constant sets (`SECRET_ENV_KEYS`, `_QUIET_PATHS`).

### Logging

```python
logger = logging.getLogger(__name__)
logger.info("[module.action] key=%s value=%r", key, value)
```

- One `logger` per module.
- Bracket-prefixed context tags: `[agent.start]`, `[chat.dispatch]`.
- Always attach `exc_info=True` to warning/error calls that catch exceptions.

### Error Handling

- `ValueError` for validation errors, caught at API boundaries and returned as 400.
- `RuntimeError` for precondition failures.
- Defensive `except Exception` with log-and-continue for non-critical paths (fallback to defaults).

### Testing

- **pytest** with `pytest-asyncio` (`asyncio_mode = "auto"`).
- Test files mirror source: `test_<module>.py`.
- Group related tests in `class Test<Topic>:` with `test_<scenario>` methods.
- Isolation via `autouse` fixtures: `_isolate_data_dir` (tmp_path + monkeypatch), `_reset_singletons`.
- Mock with `unittest.mock.patch` / `AsyncMock` / `MagicMock`, applied as decorators.
- Route tests use `aiohttp.test_utils.TestClient`.
- Mark slow tests with `@pytest.mark.slow` (skipped unless `--run-slow`).

## Frontend (`app/frontend/`)

### Style and Tooling

- **React 19** + **TypeScript** (strict mode) + **Vite**.
- No component library -- all custom HTML + CSS.
- Single global CSS file with BEM-like class naming (`block__element--modifier`).
- CSS custom properties for design tokens (`--gold`, `--surface`, `--radius`).
- Dark theme only.

### Components

- All functional components using named function declarations: `export default function TopBar({ onTogglePanel }: Props)`.
- Props defined via local `interface Props` above the component. No `React.FC`.
- Sub-components are non-exported `function` declarations co-located in the same file.
- Pages are lazy-loaded with `lazy(() => import(...))` + `<Suspense>`.
- React Router v7 with `BrowserRouter`.

### State Management

- `useState` / `useCallback` / `useRef` only. No global state library.
- Custom hooks return plain objects: `{ authenticated, loading, login, logout }`.
- Side effects in `useEffect` with cleanup returns.

### File Naming

| Type | Convention | Example |
|------|-----------|---------|
| Components | `PascalCase.tsx` | `TopBar.tsx` |
| Hooks | `camelCase.ts` with `use` prefix | `useAuth.ts` |
| Pages | `PascalCase.tsx` | `SetupWizard.tsx` |
| Utilities | `camelCase.ts` | `api.ts`, `types.ts` |

### API Layer

- Central `api<T>(path, opts)` generic wrapper around `fetch` with Bearer auth from `localStorage`.
- `apiFormData()` for multipart uploads.
- `createChatSocket()` returning a `ChatSocket` interface for WebSocket.
- Mock mode via `VITE_MOCK=1`.

### Types

- Centralized in `types.ts`. Use `interface` for object shapes, `type` for unions.
- `import type` for type-only imports.

### Testing

- **Playwright E2E only** (no unit tests).
- `mockApi(page)` and `bypassAuth(page)` helpers for test isolation.
- Mock data constants prefixed with `MOCK_`.

## Plugins and Skills

### Skills

Markdown files named `SKILL.md` with YAML frontmatter:

```yaml
---
name: web-search
description: 'Search the web using a search engine'
metadata:
  verb: search
---
```

Body contains natural-language instructions for the agent.

### Plugins

Directory with `PLUGIN.json` manifest:

```json
{
  "id": "foundry-agents",
  "name": "Microsoft Foundry Agents",
  "skills": ["foundry-code-interpreter", "foundry-agent-chat"],
  "dependencies": { "cli": ["az"], "pip": ["azure-ai-projects"] }
}
```

Plugins bundle multiple skills and declare their dependencies.

## General Principles

- Keep dependencies minimal. No unnecessary frameworks or libraries.
- Prefer composition over inheritance.
- Use dispatch tables over long if/elif chains.
- Every module has a single-line docstring describing its purpose.
- Security defaults to locked-down: auth required on all API routes, whitelist-based channel access.
- Deferred imports to break circular dependencies when needed.
- Thread-safe file I/O via locks in shared stores.
- `__all__` in `__init__.py` files to control public API surface.
