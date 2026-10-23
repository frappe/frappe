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

`concurrent=True` lets a tool run alongside the other concurrent tools the model calls in the same turn; every other tool runs on its own.

`ends_run=True` ends the run after a turn that calls only such tools, none failing: no model turn follows.

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
| `write` | `path`, `content` | Yes | Creates parent directories and overwrites the file. |
| `edit` | `path`, `edits` | Yes | Applies non-overlapping exact replacements. Every old value must appear exactly once. |
| `subagent` | `task`, `description`, `agent?`, `subagent_id?` | No | Runs a sub-agent inside the session and returns its final answer, or continues an earlier one. See [Sub-agents](#sub-agents). |

Every tool's output is capped at 2,000 lines or 50 KB. `bash` keeps the tail and saves oversized full output to a temporary log; reading, search and `subagent` keep the head. Any other tool keeps its start (1,600 lines or 40 KB) and end (400 lines or 10 KB), with a note between them telling the model to ask for less. `edit` returns a unified diff in `details` and preserves BOM and line-ending style.

Paths for `read`, `write`, `edit`, and `grep` are resolved from `cwd`. With `FLOW_ALLOWED_ROOTS`, those tools reject targets outside the configured roots, including symlink escapes. A tenant may also opt into `ignore_hidden_files`, which rejects dot-prefixed descendants and excludes them from recursive grep. This is a path policy, not a sandbox: `bash` can still access anything the daemon process can access.

## Sub-agents

`subagent` runs a child agent inside the session and returns only its final text, with `[subagent_id: <id>]` appended so the model can continue it. The child starts from a fresh context: its system prompt plus the task, nothing of the session's conversation. Unless the call names an agent, the child is `general`: a copy of the caller with the same model, prompt and tools, minus `subagent` itself (and its line in the prompt's tool list). Sub-agents cannot start sub-agents.

`SessionConfig.subagents` lists the other agents the model may name, each with a `name` and a `description`, and any of `model`, `api_key`, `api_base`, `model_params`, `reasoning_effort`, `system_prompt`, `tools`, `extension_tools`, `client_tools`, `confirm_tools`, `max_turns` and `user_context`; an unset field inherits the session's value. The model, its credentials and its `model_params` travel together: setting any of the four replaces all four. With only `model` set, the key comes from the daemon's store; a set `api_key` or `api_base` is used as given, as for the session's own fields. An agent's inline credentials and `model_params` fall under the same server policy as the session's, and its tools under the same allowlist. A child's client tools are dispatched to the session's `callback_url` with the child's `user_context`, so the host can tell which agent is calling. An inherited prompt keeps the session's tool list, so an agent with different tools should set its own prompt; an own prompt is used as written, without the session's `system_append`. The tool's description lists every agent, so the model picks one by name. The list is fixed when the session is created.

The child's events go into the session's own log, each tagged with `subagent_id`: the id of the tool call that started the child. The session's transcript skips tagged rows, so a rewind never lands inside a child, and the child's usage counts toward the session's totals. In-process `before_tool_call` and `after_tool_call` hooks passed to the run apply inside its children too.

`subagent` calls made in the same reply run at the same time, up to `max_concurrent_subagents` (default 5); their hooks and gates are checked in order first, then the batch runs, while calls of other tools keep running one at a time in order. Abort stops every running child. A child that ends without a final answer, by error, abort, turn limit or budget, returns an error result naming the reason, and the session carries on. A gated tool inside a child pauses only the child: the session keeps running, and the batch is answered through `resume` with its `approval_seq`, or abandoned with `cancel_pending`, like the session's own; a denied or cancelled child ends the same way. A change of approval mode reaches a running child's next gate, as it does the session's; the confirm list is the child's own, or the session's as of its start.

Pass `subagent_id` instead of `agent` to continue an earlier child with its context intact: it runs as the agent it started as, and its new rows keep its id. The child is rebuilt from the log, so this works after a restart too; a pause a crash left behind is cancelled first, and calls an abort left open are closed as interrupted. A child that is still running cannot be continued.

The web UI shows a sub-agent as a row in the session's thread that opens the child's own thread in a tab of the workspace panel, and asks a child's approvals in the composer with a `Sub-agent` pill. The TUI indents a child's rows under the session's.

## Bundled tools

Shipped with the harness but off by default: the default `tools` list is `bash`, `read`, `write`, `edit`, `subagent`. A session enables a bundled tool by naming it in `tools`; the web UI lists them unticked in the preset editor (the Default preset included), and `GET /tools` marks them with `"bundled": true`.

| Tool | Arguments | Default confirmation | Behavior |
| --- | --- | --- | --- |
| `grep` | `pattern`, `path?`, `include?` | No | Searches with ripgrep when available, otherwise `grep`. `include` limits the search to matching file names (`*.py`, `*.{js,vue}`), with at most one `{a,b}` group. Skips `node_modules` and binary files. Keeps the head of the output. |
| `suggest_replies` | `replies`, `multi_select?` | No | Offers the user two to four next messages after a reply, in `details`. The web UI shows them as buttons under the reply: a tap sends one, or, with `multi_select`, ticks several to send together. A turn that only calls it ends the run. |

## Extensions

An extension adds tools and tool hooks to a running daemon: Python loaded from `~/.flow/extensions/` or an explicit `-e/--extension PATH`, with no change to Flow's own source. A session gets every loaded extension tool unless it names a subset in `extension_tools`, and an extension tool overrides a built-in of the same name. See [extensions.md](extensions.md).

## Client-side tools and hooks

A client can provide JSON schemas in `SessionConfig.client_tools` with a `callback_url`, optional `callback_token`, and `user_context`. Flow sends `execute` or `confirm` callbacks containing the session id, tool, arguments, and user context. The token is sent as `X-Harness-Token`, and `callback_headers` go on every callback too, for a host that routes requests by a header (a Frappe bench names the site). A callback may return its result directly or in `{"message": ...}`. `callback_timeout` is how many seconds Flow waits for a callback to answer (default 120). An `execute` callback also carries a `result_token`; a client that runs the tool in the background can answer `{"pending": true, "timeout": N}` at once, then post `{"token": ..., "content": ..., "is_error": ...}` to `POST /sessions/{sid}/tool_result` within N seconds. Aborting the run stops the wait, not the client's job; a job can ask `POST /sessions/{sid}/tool_waiting` before it starts and skip the tool when nothing waits. A client tool may carry a `display_template` beside its schema, e.g. `{"type": "function", "function": {...}, "display_template": "Reading {{ doctype }}"}`; it works as for server tools and is not sent to the model.

With `notify_run_ended`, Flow also posts `{"callback_type": "run_ended", "session_id": ..., "terminal_seq": ...}` to `callback_url` when a run ends, and retries until the client answers with a 2xx: after 1, 5, 15 and 30 seconds, then every minute. Until then a `<session_id>.run_end_pending` file sits beside the session's log, so a restarted daemon sends the report again, also for a run it stopped in the middle of. The log stays the source of truth, so a client can get the same report twice.

Embedded Python callers can instead pass `before_tool_call` and `after_tool_call` to `Agent.run` or `Agent.resume`. The before hook can rewrite arguments or supply a result; the after hook can replace result text. Hooks are in-process only and are never stored or sent over HTTP.
