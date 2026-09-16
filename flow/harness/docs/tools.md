# Tools

Tools are async Python functions exposed to the model as function schemas. They return text for the model plus optional structured data for clients.

```python
from flow_harness.tools import ToolContext, ToolResult, tool

@tool(
    requires_confirmation=True,
    prompt_snippet="Rename a file",
    display_template="Renaming {{ path }} to {{ to }}",
)
async def rename(path: str, to: str, *, ctx: ToolContext) -> ToolResult:
    """Rename a file."""
    # Do the work here.
    return ToolResult(content=f"[renamed {path} to {to}]")
```

`@tool` derives the JSON schema from the signature and docstring. The injected `ctx` argument is not visible to the model. Use `Annotated[T, "description"]` for parameter descriptions. Arguments are validated before the function runs.

`display_template` controls the tool activity text shown by clients. It accepts simple Jinja-style argument placeholders such as `{{ path }}`. Flow waits until every referenced argument is complete, then streams the rendered text as segments so clients can style template text and argument values differently. Templates that reference arguments not present in the function signature are rejected. Display templates are UI metadata and are not sent to the model provider.

`ToolContext` provides `cwd`, allowed read/write roots, an abort event, and a timeout. `ToolResult.content` goes to the model; `details` is for clients and logs only. Return `ToolResult(is_error=True, content="...")` for an expected failure.

## Confirmation

Set `requires_confirmation=True` for a tool's default gate. A session also gates names in `confirm_tools`. `auto_approve: true` skips every confirmation gate.

When Flow reaches a gated call, it saves `approval_required` and ends the run with reason `paused`. Resume by answering every pending call: `Approve` executes it, `Deny` returns a denial and ends the run, and any other text redirects the model. This state is durable across reconnects and restarts.

## Built-in tools

| Tool | Arguments | Default confirmation | Behavior |
| --- | --- | --- | --- |
| `bash` | `command`, `timeout?` | Yes | Runs in `cwd`, combines output, records exit code, and kills its process group on timeout or abort. |
| `read` | `path`, `offset?`, `limit?` | No | Reads text with 1-indexed paging. |
| `read_file` | `path`, `offset?`, `limit?` | No | Alias for `read`, for clients that already have a tool named `read`. Selectable by name, not listed by `GET /tools`. |
| `write` | `path`, `content` | Yes | Creates parent directories and overwrites the file. |
| `edit` | `path`, `edits` | Yes | Applies non-overlapping exact replacements. Every old value must appear exactly once. |

Tool output is capped at 2,000 lines or 50 KB. `bash` keeps the tail and saves oversized full output to a temporary log; reading and search keep the head. `edit` returns a unified diff in `details` and preserves BOM and line-ending style.

Paths for `read`, `write`, `edit`, and `grep` are resolved from `cwd`. With `FLOW_ALLOWED_ROOTS`, those tools reject targets outside the configured roots, including symlink escapes. A tenant may also opt into `ignore_hidden_files`, which rejects dot-prefixed descendants and excludes them from recursive grep. This is a path policy, not a sandbox: `bash` can still access anything the daemon process can access.

## Bundled tools

Shipped with the harness but off by default: the default `tools` list is `bash`, `read`, `write`, `edit`. A session enables a bundled tool by naming it in `tools`; the web UI lists them unticked in the preset editor (the Default preset included), and `GET /tools` marks them with `"bundled": true`.

| Tool | Arguments | Default confirmation | Behavior |
| --- | --- | --- | --- |
| `grep` | `pattern`, `path?` | No | Searches with ripgrep when available, otherwise `grep`. Keeps the head of the output. |

## Extensions

The CLI can load server extensions from `~/.flow/extensions/` or explicit `-e/--extension PATH` values. `--no-extensions` disables the global directory but keeps explicit paths.

An extension is a `.py` file, or a directory with `extension.py`, exposing a synchronous `setup(flow)` function:

```python
from flow_harness.tools import ToolContext, ToolResult, tool

@tool(prompt_snippet="Greet a person", display_template="Greeting {{ name }}")
async def hello(name: str, *, ctx: ToolContext) -> ToolResult:
    return ToolResult(content=f"Hello, {name}!")

def setup(flow) -> None:
    flow.register_tool(hello)
```
An extension can also hook tool execution with `flow.on(event, handler)`. A `tool_call` handler runs before a tool executes — ahead of any approval gate, so approval prompts show the effective arguments, and a rewrite is recorded in the result's `details.effective_arguments` — and can return `PreToolUseDecision(block=True, reason=...)` to stop the call or `PreToolUseDecision(arguments=...)` to rewrite it; a `tool_result` handler runs after and can return `PostToolUseOverride(content=..., details=...)` to rewrite what the model sees (`details` replaces the tool's whole dict — spread `event.result.details` to keep existing keys). A resumed approval re-checks blocking only; approved arguments run as approved. Handlers may be sync or async and return `None` to pass. A raising `tool_call` handler blocks the call (fail-safe); a raising `tool_result` handler is skipped and the result stands. A `tool_call` handler can run more than once for the same call — a gated call is checked before the approval prompt and again when it resumes — so keep handlers side-effect free. Payload types live in `flow_harness.extensions.hooks`.

```python
from flow_harness.extensions import PreToolUseDecision

def gate(event):
    if event.tool_name == "bash" and "rm -rf" in str(event.arguments):
        return PreToolUseDecision(block=True, reason="destructive command blocked")

def setup(flow) -> None:
    flow.on("tool_call", gate)
```

Extension load errors are diagnostics, not daemon failures — and hook failures at runtime are recorded the same way (once per distinct failure) and appear in `GET /sessions/{id}/extensions`, which also lists each extension's hook subscriptions alongside its tools. Extension tools override selected built-ins with the same name; the first extension to register a duplicate name wins. Extensions are trusted Python code with the daemon's permissions.

`POST /extensions/reload` (TUI and web UI: `/reload`) re-discovers and re-imports all extensions. Sessions use the recomposed tools from their next run — an active run finishes with the tools it started with, and system prompts stay as composed at session creation.

## Client-side tools and hooks

A client can provide JSON schemas in `SessionConfig.client_tools` with a `callback_url`, optional `callback_token`, and `user_context`. Flow sends `execute` or `confirm` callbacks containing the session id, tool, arguments, and user context. The token is sent as `X-Harness-Token`, and `callback_headers` go on every callback too, for a host that routes requests by a header (a Frappe bench names the site). A callback may return its result directly or in `{"message": ...}`. `callback_timeout` is how many seconds Flow waits for a callback to answer (default 120).

Embedded Python callers can instead pass `before_tool_call` and `after_tool_call` to `Agent.run` or `Agent.resume`. The before hook can rewrite arguments or supply a result; the after hook can replace result text. Hooks are in-process only and are never stored or sent over HTTP.
