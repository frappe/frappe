# API

Two entry points over the same engine: the in-process **`Agent`** (blocking async
iteration, for embedding/tests/TUI) and the **HTTP API** (remote, disconnect-tolerant).

## In-process: `Agent`

```python
from flow.agent import Agent
```

### Constructor

```python
Agent(config: SessionConfig | None = None, *, data_dir="~/.flow/server", **overrides)
```

- Pass a `SessionConfig`, or pass its fields as keyword `**overrides`.
- `model=` accepts a **name string** (resolved via `get_model`, e.g. `"openai/gpt-4o"`,
  `"mock"`) or a pre-built **`Model` instance** (injected directly — used by tests and
  embedders).
- `data_dir` is where the durable log is written. It defaults to the user-global
  `~/.flow/server`; pass an explicit path for isolated embedded instances.

### Methods

```python
agent.run(message: str, **hooks) -> AsyncIterator[Event]        # start a turn
agent.resume(answers: dict[str, str], *, approval_seq: int | None = None, **hooks)
    -> AsyncIterator[Event]   # continue a paused run
agent.abort() -> bool         # signal the active run; false when idle/paused
agent.set_model(model: str, credential_id: str | None = None)   # switch for later runs
```

`run()` and `resume()` are async generators. `**hooks` = `before_tool_call` and/or
`after_tool_call` (see [tools.md](tools.md)); iteration ends when a `run_ended` event
is yielded. `abort()` is synchronous: it signals the same per-operation cancellation
event used by the HTTP API and returns whether an active run was found. Continue
consuming the run iterator through its terminal `run_ended(reason=="aborted")` event.
For the raw verbs (`Session.run/resume/abort/cancel_pending`, `Session.events`), use
`agent.session`.

### Examples

Streaming a turn:

```python
agent = Agent(model="openai/gpt-4o", system_prompt="You are a coding agent.",
              tools=["bash", "read_file", "write", "edit", "grep"], cwd="/proj")

async for e in agent.run("Summarize the biggest Python file."):
    if e.type == "text_delta":       print(e.text, end="", flush=True)
    elif e.type == "tool_result":    print(f"\n[{e.name}] {e.content[:80]}")
    elif e.type == "run_ended":      print(f"\n— {e.reason} —")
```

Approval pause → resume:

```python
agent = Agent(model="openai/gpt-4o", cwd=".", confirm_tools=["bash", "edit"])

pending = []
approval_seq = None
async for e in agent.run("delete the build dir"):
    if e.type == "approval_required":
        pending = e.calls                       # [PendingCall(id, name, args, prompt), ...]
        approval_seq = e.seq

answers = {c.id: "Approve" for c in pending}    # or "Deny", or free text to redirect
async for e in agent.resume(answers, approval_seq=approval_seq):
    ...
```

## HTTP API

Start the daemon: `flow serve --port 8787`. All routes are JSON unless noted. When
`FLOW_AUTH_TOKEN` is configured, send `Authorization: Bearer <token>` on every
request except `GET /healthz`.

### `GET /healthz`
`→ {"ok": true}`

### `POST /sessions`
Body: a `SessionConfig` (all fields optional; see below).
`→ {"session_id": "...", "config": {...}}` (secrets redacted). `400` if `cwd` is outside
`ALLOWED_ROOTS` or `session_id` is invalid.

### `GET /sessions/{sid}`
`→ {"session_id", "state", "running", "latest_seq", "model", "credential_id", "config"}`.
`state` is `idle`, `running`, or `paused`; `running` remains as a compatibility boolean.
`model`/`credential_id` are the effective selection — the last `model_changed` entry on
the active branch, else the creation config. `404` if unknown.

### `POST /sessions/{sid}/run?wait=<bool>`
Body: `{"message": "..."}`. A run always uses the session's current model selection;
to switch, use `POST /sessions/{sid}/model` before the run.
- default (`wait` false): starts the run as a background task → `{"status": "started"}`.
  If a run is already active, the message is queued as steering → `{"status": "steered"}`
  (returned immediately even with `?wait=true`).
- `?wait=true`: blocks until the started run ends →
  `{"reason", "output", "usage", "pending", "approval_seq"}` (`output` = final
  assistant text; `pending` and `approval_seq` identify the approval batch if
  `reason=="paused"`). A model token-limit stop returns `reason=="length"` rather than
  being reported as a completed answer.
- `409` if the session is paused; resolve that batch through `/resume` (or abandon it
  through `/cancel_pending`) before starting another run. A run that has already
  received `/abort` also rejects new steering with `409` instead of carrying it into a
  later turn.

### `POST /sessions/{sid}/resume?wait=<bool>`
Body:
`{"approval_seq": 12, "answers": {"<tool_call_id>": "Approve" | "Deny" | "<free text>"}}`.
`approval_seq` must identify the current `ApprovalRequired` event and `answers` must
contain exactly its unresolved call ids. Missing, extra, stale, already-resolved, and
not-paused requests return `409` without changing the log. Same fire-and-forget /
`?wait` shapes as `/run`.

### `POST /sessions/{sid}/abort`
Signals active work to stop and clears steering that has not yet entered the durable
transcript →
`{"status": "aborting" | "idle" | "paused"}`.
Model streams, provider HTTP bodies, hooks, tools, Bash process groups, and client-tool
callback requests are interrupted. A completed cancellation persists an
`assistant_message` with `stop_reason=="aborted"` followed by
`run_ended(reason=="aborted")`; the session then returns to `idle`. Calling this
endpoint for an idle or approval-paused session is a no-op; to abandon a paused
session's approval batch, use `/cancel_pending`.

### `POST /sessions/{sid}/cancel_pending`
Abandons a paused session's approval batch: every undecided call is answered with a
cancellation `tool_result` (`is_error: true`), the transcript closes, and the session
returns to idle →
`{"status": "cancelled"}`, or `{"status": "idle" | ...}` when nothing was pending.
`409` while a run is active.

### `POST /sessions/{sid}/rewind`
Body: `{"target_seq": 12}`. Moves the conversation back to that entry; the next run
branches from it. Nothing is deleted — the abandoned rows stay in the log, off the
active path. `target_seq: 0` rewinds to before everything; to edit a message, rewind
to the entry before its run (or `0` for the first run). Any other target must exist
and leave a clean tail (no unanswered tool calls, no pending approval); rewinding a
paused session abandons its approval batch →
`{"status": "rewound"}`. `409` while a run is active or for an invalid target.

### `POST /sessions/{sid}/model`
Body: `{"model": "provider/model", "credential_id": "optional-name"}`. Selects the
model (and stored credential) for runs from here on, as a durable `model_changed`
entry in the log — so it survives restarts and is per-branch: a rewind to before the
change restores the previous selection. Setting the already-active selection writes
nothing. Provider keys, OAuth tokens, headers, and base URLs are never accepted;
they are resolved inside flow →
`{"model": "...", "credential_id": ...}` (the now-effective selection). `409` while a
run is active; allowed while paused (the resume continues on the new model).

### `GET /sessions/{sid}/entries?since=<int>&path=<active|all>`
The durable log →
`{"entries": [...], "latest_seq", "state", "running"}`.
Default (`active`) is the branch the conversation is on — what a renderer should show;
for a session that was never rewound this is simply the whole log. It is a snapshot:
a rewind can retract rows before any cursor, so combining it with `since` is a `422`.
`path=all` is raw file order — including abandoned branches and the `rewind` markers —
and accepts `since`. To catch up after a disconnect, replay `/stream?since=N` (you
will see any `rewind` marker) or refetch the active view whole.

### `GET /sessions/{sid}/stream?since=<int>`
Server-Sent Events. Replays durable entries with `seq > since`, then streams live
events. Each line: `data: {<event json>}\n\n`. The stream closes when the watched run
ends (`run_ended`, including `reason=="paused"`); for a session with no active run it
closes after the replay. Reconnect after a drop by passing `since=<last seq you saw>` —
the continuation is gapless and duplicate-free.

Durable `assistant_message` entries contain an ordered `content` array of `text`,
`thinking`, and `tool_call` blocks plus `api`, `provider`, `model`, optional upstream
response identity, and `stop_reason`. Tool-call input is named `arguments` inside that
array. Provider round-trip data rides in the opaque `provider_state` field on content
blocks.

### Example client

```python
import httpx, json
c = httpx.Client(base_url="http://127.0.0.1:8787", timeout=None)

sid = c.post("/sessions", json={
    "model": "gpt-4o", "tools": ["bash", "read_file", "write", "edit", "grep"],
    "cwd": "/proj", "confirm_tools": ["read_file"],
}).json()["session_id"]

# fire-and-forget + stream (survives disconnect)
c.post(f"/sessions/{sid}/run", json={"message": "summarize the repo"})
with c.stream("GET", f"/sessions/{sid}/stream", params={"since": 0}) as r:
    for line in r.iter_lines():
        if line.startswith("data:"):
            ev = json.loads(line[5:])
            if ev["type"] == "text_delta": print(ev["text"], end="")
            if ev["type"] == "run_ended": break

# or blocking
res = c.post(f"/sessions/{sid}/run", params={"wait": "true"},
             json={"message": "what is 2+2?"}).json()
print(res["output"], res["reason"], res["usage"])
```

## `SessionConfig` fields

| Field | Default | Notes |
|---|---|---|
| `session_id` | generated | client-provided id (must be `[A-Za-z0-9_-]{1,64}`) |
| `model` | `"mock"` | name string; prefix selects the provider. The initial selection — switch later via `POST /sessions/{sid}/model` (config never mutates) |
| `system_prompt` | `"You are a helpful agent."` | |
| `tools` | `["bash","read_file","write","edit","grep"]` | builtin tool names |
| `client_tools` | `[]` | schemas for tools the client runs (see [tools.md](tools.md)) |
| `callback_url` / `callback_token` | none | where/how client tools are dispatched |
| `user_context` | `{}` | opaque data echoed on callbacks |
| `credential_id` | inferred | named credential selected for the model |
| `confirm_tools` | `[]` | extra tools that pause for approval, on top of each tool's own default |
| `auto_approve` | `false` | unattended runs skip approval |
| `cwd` | `"."` | tool working dir; cwd and built-in file paths are checked against `ALLOWED_ROOTS` (`bash` is not sandboxed) |
| `max_turns` | `30` | turn cap |
| `max_output_tokens` | `200000` | output-token spend cap |
| `stream` | `true` | consume the model as a token stream |
