# Extensions

An extension is Python that the daemon imports at startup to add tools and to hook tool execution. It is how Flow is customized: a capability belongs in an extension, not in a patch to Flow's own source, so an upgrade never has to be re-applied by hand and a deployment can carry only what it needs.

Extensions are trusted code. They run inside the daemon process with the daemon's permissions, with no sandbox between them and the host.

## Where extensions live

The daemon loads `~/.flow/extensions/` plus any explicit `-e/--extension PATH` (repeatable). `--no-extensions` drops the global directory and keeps the explicit paths; the deployed profile skips the global directory too, so an operator opts in per path. A daemon serving many sites also loads each site's own `extensions` paths from the tenants file into that site's partition alone (see [api.md](api.md)), so one site's tools and hooks never reach another.

An extension is either a single `.py` file, or a directory holding `extension.py`. Names starting with `.` or `_` are skipped when a directory is scanned. The extension's name is the file stem or the directory name, and the first of a duplicate name wins — the rest are ignored with a diagnostic.

A directory is imported as a package, so its own modules are siblings:

    ~/.flow/extensions/
      hello.py            # name: hello
      review/
        extension.py      # name: review
        prompts.py        # from . import prompts

## The entry point

Every extension defines a synchronous `setup(flow)`, called once at load with an `ExtensionAPI`:

```python
from flow_harness.extensions import ExtensionAPI

def setup(flow: ExtensionAPI) -> None:
    flow.register_tool(hello)
    flow.on("tool_call", gate)
```

`setup` may raise — the extension is dropped, its registrations are rolled back, and the failure is recorded as a diagnostic. It must not be `async`.

## Registering a tool

An extension tool is an ordinary Flow tool (see [tools.md](tools.md)): `@tool` derives the model-visible schema from the signature and docstring, and `ctx` is injected rather than asked of the model.

```python
from flow_harness.tools import ToolContext, ToolResult, tool

@tool(prompt_snippet="Greet a person", display_template="Greeting {{ name }}")
async def hello(name: str, *, ctx: ToolContext) -> ToolResult:
    """Greet someone by name."""
    return ToolResult(content=f"Hello, {name}!")

def setup(flow: ExtensionAPI) -> None:
    flow.register_tool(hello)
```

A session gets every loaded extension tool unless it names a subset in `extension_tools`. An extension tool overrides a built-in of the same name, and the first extension to claim a name keeps it; `GET /tools` still lists the built-in, so leaving the extension tool out of `extension_tools` gives it back.

Respect `ctx.abort` and `ctx.timeout` in anything long-running, and set `requires_confirmation=True` on anything destructive so the call goes through the approval gate.

## Hooking tool calls

`flow.on(event, handler)` subscribes to `tool_call` (before a tool runs) or `tool_result` (after). Handlers may be sync or async, run in load order, and return `None` to pass. Payload types live in `flow_harness.extensions.hooks`.

```python
from flow_harness.extensions import PreToolUseDecision

def gate(event):
    if event.tool_name == "bash" and "rm -rf" in str(event.arguments):
        return PreToolUseDecision(block=True, reason="destructive command blocked")

def setup(flow: ExtensionAPI) -> None:
    flow.on("tool_call", gate)
```

`tool_call` receives `tool_name`, `arguments`, and `cwd`, and returns `PreToolUseDecision(block=True, reason=...)` to stop the call, or `PreToolUseDecision(arguments=...)` to rewrite it. Blocking wins over a rewrite and short-circuits the handlers after it. Each handler sees the arguments as the one before it left them, and a rewrite reaches the result's `details.effective_arguments`. The hook runs ahead of the approval gate, so a prompt shows the arguments that will actually run — which also means a gated call is checked twice, once before the prompt and again when it resumes, so keep handlers side-effect free. A resumed approval re-checks blocking only; arguments approved by a user run as approved. A raising `tool_call` handler blocks the call: a broken gate must not let one through.

`tool_result` receives `tool_name`, the effective `arguments`, and the `result`, and returns `PostToolUseOverride(content=..., details=...)` to rewrite what the model sees. `details` replaces the tool's whole dict, so spread the old keys to keep them: `details={**event.result.details, "extra": 1}`. A raising `tool_result` handler is skipped and the result stands.

## Dependencies

An extension is imported into the running daemon, so whatever it imports must already be installed in the environment that runs `flow serve`. Flow's own `pyproject.toml` is not the place to declare it: the point of an extension is a capability added without touching Flow's source, and a dependency added there would ship to every install of Flow, for everyone.

Install into the daemon's environment instead — the same interpreter that runs `flow serve`, which on a Frappe bench is the bench env:

    ./env/bin/pip install playwright
    ./env/bin/playwright install chromium

Import the dependency inside the tool function rather than at module scope. At module scope a missing package is an `ImportError` at load time and the whole extension is dropped; inside the function it costs one call and returns a message the model and the user can act on.

```python
@tool(prompt_snippet="Screenshot a URL")
async def screenshot(url: str, *, ctx: ToolContext) -> ToolResult:
    """Capture a PNG of a page."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return ToolResult(content="playwright is not installed in the daemon environment", is_error=True)
```

A self-contained extension can vendor its dependencies instead. Make it a directory extension, install into it, and put the directory on `sys.path` before importing — the loader makes an extension directory a package, which covers `from . import sibling`, but not an absolute import of something vendored inside it:

    pip install --target ~/.flow/extensions/browser/vendor playwright

```python
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "vendor"))
```

Some packages also carry assets that pip does not place, such as Playwright's browsers; those need their own install step, and a `PLAYWRIGHT_BROWSERS_PATH` (or equivalent) when the daemon runs as a different user than the one that installed them.

Installing or upgrading a dependency takes a daemon restart. `POST /extensions/reload` re-imports extension modules only — every third-party package already imported stays in `sys.modules`, so a reload keeps using the version that was loaded first.

Tools run on the daemon's event loop, which a blocking call stalls for every session on it. Use a package's async API where it has one, and `asyncio.to_thread` where it does not.

## Reloading

`POST /extensions/reload` (`/reload` in the TUI and web UI) re-discovers and re-imports every extension. Sessions pick up the recomposed tools on their next run: a run already in flight finishes with the tools it started with, and system prompts stay as they were composed at session create.

## Diagnostics

A load failure is never fatal to the daemon. Failures — a bad import, a missing or async `setup`, a duplicate name, a handler that raised — are collected as diagnostics and reported by `GET /sessions/{id}/extensions`, which also lists each extension's tools and hook subscriptions. A repeated runtime failure is recorded once per distinct message, since hooks run on every tool call. The CLI prints load diagnostics to stderr at startup.

## Listing tools

`flow extension-tools PATH...` loads the given extension files or directories the way `flow serve -e` would, prints one JSON row per registered tool (`name`, `description`, `extension`) on stdout, and reports load problems on stderr, along with anything an extension prints while it loads, so stdout stays valid JSON. A client that fronts the daemon uses it to learn the tool names before the daemon starts, for example to build a `tool_allowlist` and a tool picker.

## Examples

Working extensions live in [examples/extensions/](../examples/extensions/):

| Example | Shows |
| --- | --- |
| `hello_tool.py` | The smallest extension: one tool, one `setup`. |
| `protected_paths.py` | A `tool_call` hook that blocks `write` and `edit` on sensitive filenames; `bash` is not covered. |
| `redact_secrets.py` | A `tool_result` hook that rewrites what the model sees. |
| `browser/` | A directory extension with a third-party dependency, imported lazily and run off the event loop. |
