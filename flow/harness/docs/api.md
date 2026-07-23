# API

Two entry points over the same engine: the in-process **`Agent`** (blocking async
iteration, for embedding/tests/TUI) and the **HTTP API** (remote, disconnect-tolerant).

## In-process: `Agent`

```python
from flow_server.agent import Agent
```

### Constructor

```python
Agent(config: SessionConfig | None = None, *, data_dir=".flow-data", **overrides)
```

- Pass a `SessionConfig`, or pass its fields as keyword `**overrides`.
- `model=` accepts a **name string** (resolved via `get_model`, e.g. `"gpt-4o"`,
  `"mock"`) or a pre-built **`Model` instance** (injected directly — used by tests and
  embedders).
- `data_dir` is where the durable log is written.

### Methods — both are async generators yielding events

```python
agent.run(message: str, **hooks) -> AsyncIterator[Event]        # start a turn
agent.resume(answers: dict[str, str], **hooks) -> AsyncIterator[Event]   # continue a paused run
```

`**hooks` = `before_tool_call` and/or `after_tool_call` (see [tools.md](tools.md)).
Iteration ends when a `run_ended` event is yielded.

### Examples

Streaming a turn:

```python
agent = Agent(model="gpt-4o", system_prompt="You are a coding agent.",
              tools=["bash", "read_file", "write", "edit", "grep"], cwd="/proj")

async for e in agent.run("Summarize the biggest Python file."):
    if e.type == "text_delta":       print(e.text, end="", flush=True)
    elif e.type == "tool_result":    print(f"\n[{e.name}] {e.content[:80]}")
    elif e.type == "run_ended":      print(f"\n— {e.reason} —")
```

Approval pause → resume:

```python
agent = Agent(model="gpt-4o", cwd=".", confirm_tools=["bash", "edit"])

pending = []
async for e in agent.run("delete the build dir"):
    if e.type == "approval_required":
        pending = e.calls                       # [PendingCall(id, name, args, prompt), ...]

answers = {c.id: "Approve" for c in pending}    # or "Deny", or free text to redirect
async for e in agent.resume(answers):
    ...
```

## HTTP API

Start the daemon: `flowd serve --port 8787`. All routes are JSON unless noted.

### `GET /healthz`
`→ {"ok": true}`

### `POST /sessions`
Body: a `SessionConfig` (all fields optional; see below).
`→ {"session_id": "...", "config": {...}}` (secrets redacted). `400` if `cwd` is outside
`ALLOWED_ROOTS` or `session_id` is invalid.

### `GET /sessions/{sid}`
`→ {"session_id", "running", "latest_seq", "config"}`. `404` if unknown.

### `POST /sessions/{sid}/run?wait=<bool>`
Body: `{"message": "..."}`.
- default (`wait` false): starts the run as a background task → `{"status": "started"}`.
  If a run is already active, the message is queued as steering → `{"status": "steered"}`.
- `?wait=true`: blocks until the run ends → `{"reason", "output", "usage", "pending"}`
  (`output` = final assistant text; `pending` = approval calls if `reason=="paused"`).

### `POST /sessions/{sid}/resume?wait=<bool>`
Body: `{"answers": {"<tool_call_id>": "Approve" | "Deny" | "<free text>"}}`.
Same fire-and-forget / `?wait` shapes as `/run`. `409` if a run is currently active.

### `POST /sessions/{sid}/abort`
Signals the run to stop at the next boundary → `{"status": "aborting" | "idle"}`.

### `GET /sessions/{sid}/entries?since=<int>`
The durable log from the cursor → `{"entries": [...], "latest_seq", "running"}`.

### `GET /sessions/{sid}/stream?since=<int>`
Server-Sent Events. Replays durable entries with `seq > since`, then streams live events
until `run_ended`. Each line: `data: {<event json>}\n\n`. Reconnect after a drop by
passing `since=<last seq you saw>`.

### Example client

```python
import httpx, json
c = httpx.Client(base_url="http://127.0.0.1:8787", timeout=None)

sid = c.post("/sessions", json={
    "model": "gpt-4o", "tools": ["bash", "read_file", "edit", "grep"],
    "cwd": "/proj", "confirm_tools": ["bash", "edit"],
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
| `model` | `"mock"` | name string; prefix selects the provider |
| `system_prompt` | `"You are a helpful agent."` | |
| `tools` | `["bash","read_file","edit","grep"]` | builtin tool names |
| `client_tools` | `[]` | schemas for tools the client runs (see [tools.md](tools.md)) |
| `callback_url` / `callback_token` | none | where/how client tools are dispatched |
| `user_context` | `{}` | opaque data echoed on callbacks |
| `api_key` / `api_base` | none | per-session model credentials |
| `confirm_tools` | `[]` | tools that pause for approval (overrides tool defaults) |
| `auto_approve` | `false` | unattended runs skip approval |
| `cwd` | `"."` | tool working dir (fenced by `ALLOWED_ROOTS`) |
| `max_turns` | `30` | turn cap |
| `max_output_tokens` | `200000` | output-token spend cap |
| `stream` | `true` | consume the model as a token stream |
