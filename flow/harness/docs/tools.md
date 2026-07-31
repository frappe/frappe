# Tools

A tool is a Python async function wrapped by `@tool`. The decorator derives the
model-facing JSON schema from the signature and docstring, so there's one source of
truth. Everything lives in `tools/`.

## The model

```python
from flow_server.tools.tool import tool, Tool, ToolContext, ToolResult
```

- **`Tool`** — `name`, `description`, `parameters` (JSON schema), `func`,
  `requires_confirmation`, `confirm_prompt`. `Tool.__call__(**kwargs)` runs the function
  through `pydantic.validate_call`, so model-supplied args are coerced/validated before
  your body runs (bad args raise `ValidationError`, which the loop turns into an error
  result). `to_schema()` produces the OpenAI function-tool schema.
- **`ToolContext`** — runtime state injected by the loop, never seen by the model:
  `cwd`, `allowed_roots`, `abort` (the active operation's `asyncio.Event`), `timeout`.
- **`ToolResult`** — what a tool returns: `content` (the text the model sees),
  `details` (structured render metadata — diff, truncation, exit code — **never** sent
  to the model), `is_error`.

## Writing a tool

```python
from typing import Annotated
from flow_server.tools.tool import tool, ToolContext, ToolResult

@tool(requires_confirmation=True)
async def rename(
    path: str,
    to: Annotated[str, "new path, relative to cwd or absolute"],
    *,
    ctx: ToolContext,
) -> ToolResult:
    """Rename a file."""              # docstring = the model-facing description
    ...
    return ToolResult(content=f"[renamed {path} -> {to}]", details={"from": path, "to": to})
```

Rules the schema builder relies on:

- The docstring's first block becomes the tool `description`.
- `ctx` (and `self`/`cls`, `*args`, `**kwargs`) are stripped from the schema — `ctx` is
  injected by the loop, not the model.
- `Annotated[T, "text"]` attaches a param description. Types map to JSON schema:
  primitives, `Literal→enum`, `X | None→optional`, `list[T]→typed array`,
  `Union→anyOf`, Pydantic models (inlined), `Enum`. `additionalProperties` is `false`.
- Return a `ToolResult`. Do your own error handling by returning
  `ToolResult(is_error=True, content="...")`; uncaught exceptions are also caught by the
  loop and fed back to the model as an error result.

Register a builtin by adding it to `BUILTIN_TOOLS` in `tools/builtins/__init__.py`.

## Confirmation

A tool declares its default with `requires_confirmation=True` and an optional
`confirm_prompt(args) -> str` for a custom approval message. Per call, the gate is:
`auto_approve` switches approval off entirely; otherwise a call pauses when its tool is
listed in `SessionConfig.confirm_tools` **or** the tool's own default requires it.
`confirm_tools` is additive — gating a client tool never un-gates `bash`/`write`/`edit`.
When a gated call is reached, the loop finishes the turn, emits `ApprovalRequired`, and
pauses until `resume` (or `cancel_pending`).

## Builtins

Path-taking tools resolve relative paths against `ctx.cwd`. When
`FLOW_SERVER_ALLOWED_ROOTS` is configured, `read_file`, `write`, `edit`, and `grep`
realpath-check every target and reject traversal or symlink escapes. Output is truncated
to 2000 lines / 50 KB. Mutating/executing tools default
`requires_confirmation=True`; read-only ones don't.

| Tool | Args | Confirm | Notes |
|---|---|---|---|
| `bash` | `command`, `timeout?` | ✓ | combined stdout/stderr + exit code; own process group (group-killed on timeout/abort); tail-truncates, spills full output to a temp file when truncated |
| `read_file` | `path`, `offset?`, `limit?` | — | 1-indexed line paging; head-truncates with a continuation hint |
| `write` | `path`, `content` | ✓ | creates parent dirs; overwrites |
| `edit` | `path`, `edits: [{old, new}]` | ✓ | multi-edit; each `old` must occur exactly once; non-overlapping; all-or-nothing; LF-normalized match with BOM/CRLF preserved; emits a unified diff in `details` |
| `grep` | `pattern`, `path?` | — | ripgrep if available, else `grep`; the pattern is passed after `--` so it can never be read as an option; match count in `details` |

**Trust note:** `ALLOWED_ROOTS` is a path policy for the path-taking builtins, not an OS
sandbox. In particular, `bash` can access anything available to the daemon process. A
deployment that requires security containment must run shell commands in a separate
container or equivalent sandbox. Confirmation prompts reduce accidental execution but
are not a containment boundary.

## Client-side tools

A client can run its own tools instead of (or alongside) the builtins. It registers
their schemas in `SessionConfig.client_tools` and sets `callback_url` (+ optional
`callback_token`). When the model calls such a tool, the daemon POSTs to the callback
(`mode: "execute"` to run it, `mode: "confirm"` to fetch an approval prompt) with
`{session_id, tool, args, user_context, mode}` and the `X-Harness-Token` header. The
response may be the result dict itself or wrapped in a Frappe-style
`{"message": {...}}` envelope; an `execute` result is `{content, is_error}`. This is
how Flow runs tools as the logged-in user. Hooks, by contrast, are in-process only and
are never shipped over the wire.

The callback request and the surrounding tool task are both cancelled when the
session's abort signal is set. A custom async tool should still use `ctx.abort` for
cooperative cleanup of resources it owns. Synchronous tool bodies cannot be preempted
mid-call; the loop checks cancellation immediately before and after them.

## Hooks

Embedded callers may pass `before_tool_call(call, ctx)` / `after_tool_call(call,
result)` into `run`/`resume` (sync or async). `before` returns a `HookDecision`:
rewrite `args`, or short-circuit the call with `result` (+ `is_error`); `after` may
return replacement result text. Order per call: bad-args feedback → before hook →
confirm gate → dispatch → after hook. Hooks are never persisted and never cross the
HTTP boundary.
