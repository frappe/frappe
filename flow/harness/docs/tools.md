# Tools

Tools are async Python functions exposed to the model as function schemas. They return text for the model plus optional structured data for clients.

```python
from flow.tools import ToolContext, ToolResult, tool

@tool(
    requires_confirmation=True,
    prompt_snippet="Rename a file",
    display="Renaming {{ path }} to {{ to }}",
)
async def rename(path: str, to: str, *, ctx: ToolContext) -> ToolResult:
    """Rename a file."""
    # Do the work here.
    return ToolResult(content=f"[renamed {path} to {to}]")
```

`@tool` derives the JSON schema from the signature and docstring. The injected `ctx` argument is not visible to the model. Use `Annotated[T, "description"]` for parameter descriptions. Arguments are validated before the function runs.

`display` controls the tool activity text shown by clients. It accepts simple Jinja-style argument placeholders such as `{{ path }}`. Flow waits until every referenced argument is complete, then streams the rendered text as segments so clients can style template text and argument values differently. Templates that reference arguments not present in the function signature are rejected. Display templates are UI metadata and are not sent to the model provider.

`ToolContext` provides `cwd`, allowed read/write roots, an abort event, and a timeout. `ToolResult.content` goes to the model; `details` is for clients and logs only. Return `ToolResult(is_error=True, content="...")` for an expected failure.

## Confirmation

Set `requires_confirmation=True` for a tool's default gate. A session also gates names in `confirm_tools`. `auto_approve: true` skips every confirmation gate.

When Flow reaches a gated call, it saves `approval_required` and ends the run with reason `paused`. Resume by answering every pending call: `Approve` executes it, `Deny` returns a denial and ends the run, and any other text redirects the model. This state is durable across reconnects and restarts.

## Built-in tools

| Tool | Arguments | Default confirmation | Behavior |
| --- | --- | --- | --- |
| `bash` | `command`, `timeout?` | Yes | Runs in `cwd`, combines output, records exit code, and kills its process group on timeout or abort. |
| `read_file` | `path`, `offset?`, `limit?` | No | Reads text with 1-indexed paging. |
| `write` | `path`, `content` | Yes | Creates parent directories and overwrites the file. |
| `edit` | `path`, `edits` | Yes | Applies non-overlapping exact replacements. Every old value must appear exactly once. |
| `grep` | `pattern`, `path?` | No | Searches with ripgrep when available, otherwise `grep`. |

Tool output is capped at 2,000 lines or 50 KB. `bash` keeps the tail and saves oversized full output to a temporary log; reading and search keep the head. `edit` returns a unified diff in `details` and preserves BOM and line-ending style.

Paths for `read_file`, `write`, `edit`, and `grep` are resolved from `cwd`. With `FLOW_ALLOWED_ROOTS`, those tools reject targets outside the configured roots, including symlink escapes. This is a path policy, not a sandbox: `bash` can still access anything the daemon process can access.

## Extensions

The CLI can load server extensions from `~/.flow/extensions/` or explicit `-e/--extension PATH` values. `--no-extensions` disables the global directory but keeps explicit paths.

An extension is a `.py` file, or a directory with `extension.py`, exposing a synchronous `setup(flow)` function:

```python
from flow.tools import ToolContext, ToolResult, tool

@tool(prompt_snippet="Greet a person", display="Greeting {{ name }}")
async def hello(name: str, *, ctx: ToolContext) -> ToolResult:
    return ToolResult(content=f"Hello, {name}!")

def setup(flow) -> None:
    flow.register_tool(hello)
```

Extension load errors are diagnostics, not daemon failures. Extension tools override selected built-ins with the same name; the first extension to register a duplicate name wins. Extensions are trusted Python code with the daemon's permissions.

## Client-side tools and hooks

A client can provide JSON schemas in `SessionConfig.client_tools` with a `callback_url`, optional `callback_token`, and `user_context`. Flow sends `execute` or `confirm` callbacks containing the session id, tool, arguments, and user context. The token is sent as `X-Harness-Token`. A callback may return its result directly or in `{"message": ...}`.

Embedded Python callers can instead pass `before_tool_call` and `after_tool_call` to `Agent.run` or `Agent.resume`. The before hook can rewrite arguments or supply a result; the after hook can replace result text. Hooks are in-process only and are never stored or sent over HTTP.
