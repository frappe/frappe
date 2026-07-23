# Architecture

flow_server is built in layers; each only depends on the ones below it.

```
cli/            flowd serve — process entrypoint (SessionStore + create_app + uvicorn)
server/         FastAPI HTTP API + SSE  (the remote boundary)
agent/          the loop (model ↔ tools) + the in-process Agent facade   ← the heart
tools/          Tool abstraction, schema builder, builtin tools
model/          provider-neutral Model interface (litellm + native + mock) [+ auth]
session/        Session, SessionConfig, durable seq-log, live pub/sub
events.py       the event protocol — the contract everything speaks
config.py       daemon-wide defaults (env-overridable)
```

## The event protocol (`events.py`)

Every interaction is a typed event. Two families:

- **Durable** — assigned a monotonic `seq` and persisted to the log; these reconstruct
  the conversation on replay/restart.
- **Live-only** (`durable=False`) — transient token/tool deltas for a responsive UI;
  never persisted. If a client misses them, the durable log + replay heals the gap.

| Event | Durable | Meaning |
|---|---|---|
| `RunStarted` | ✓ | a turn began (`run_id`) |
| `UserMessage` | ✓ | user input added to the transcript |
| `AssistantMessage` | ✓ | assembled assistant turn (`text` + `tool_calls`) |
| `ToolResult` | ✓ | a tool's outcome (`content` seen by the model; `details` for rendering; `is_error`) |
| `Usage` | ✓ | token/cost accounting for a turn |
| `ApprovalRequired` | ✓ | the run paused; `calls` = `PendingCall`s awaiting a decision |
| `RunEnded` | ✓ | terminal; `reason` ∈ done/max_turns/budget/aborted/error/paused |
| `RunError` | ✓ | a run-level failure message |
| `TextDelta` | — | a streamed text chunk |
| `ToolCallStarted` | — | a tool call's name became known mid-stream |

`content` on a `ToolResult` is what the model sees; `details` (diff, truncation,
exit code, …) rides the durable stream for rich rendering but is **never** sent to the
model.

## The durable log (`session/log.py`)

An append-only JSONL file, one per session. `append()` assigns the next `seq`, writes,
and `fsync`s. `read_since(n)` returns every entry with `seq > n` — this is both the
**replay** path (catch a reconnecting client up) and the **restart** path (rebuild
state from disk). Durability lives here and nowhere else.

## Session & config (`session/store.py`)

- **`SessionConfig`** (a Pydantic model, sent per-session by any client) is the whole
  extensibility seam: `model`, `system_prompt`, `tools`, `client_tools`, `callback_url`,
  `confirm_tools`, `auto_approve`, `cwd`, `max_turns`, `max_output_tokens`, `stream`, …
- **`Session`** holds the live transcript (`messages`, rebuilt from the log via
  `_rebuild_messages`), an `abort` event, a `steer_queue`, and the pub/sub. `publish()`
  is the fan-out: persist-if-durable → deliver to live subscribers → forward to an
  optional sink (e.g. Redis).
- **`SessionStore`** owns create/get and enforces the security fences (below).

## The model layer (`model/`)

`Model.run(messages, tools, *, stream)` is an **async generator**: streaming yields
`TextDelta` + `ToolCallStarted`, and every turn ends with a terminal `AssistantMessage`
then a `Usage`. The loop consumes exactly this, whatever the provider underneath.

`get_model(name)` dispatches on the name's prefix: a registered native provider (the
keyless `mock`, or a Phase-3 OAuth provider) wins; everything else falls through to
`LiteLLMModel` (the broad API-key path). Auth for native OAuth providers
(`auth.py`/`credentials.py`/`providers/`) is an orthogonal branch — it only matters when
such a model runs.

## The agent loop (`agent/loop.py`) — the heart

`run()` → publish `RunStarted`, append the user message, enter `_loop`. Each turn:

1. **`_model_call`** — build `[system] + session.messages`, consume `model.run()`,
   publish deltas + `AssistantMessage` + `Usage`, return the assistant + token count.
2. append the assistant message. If it has no tool calls → `RunEnded(done)`.
3. for each tool call, **`_handle_call`** (dispatch order below).
4. if any call was confirm-gated → publish `ApprovalRequired`, stop with `paused`.
5. else check caps (`max_turns`, `max_output_tokens`, `abort`) and loop.

### Two interception layers (deliberately separate — neither substitutes for the other)

1. **`before_tool_call` / `after_tool_call`** — optional in-process Python callables
   passed straight into `run()`/`resume()`. Never serialized. `before` returns a
   `HookDecision` (rewrite `args`, or short-circuit with a synthetic/blocked `result`);
   `after` returns replacement content (post-processing/redaction). For arg rewriting,
   metrics, rate limits, cheap policy blocks, synthetic short-circuits.
2. **`confirm_tools` + `ApprovalRequired` + `resume`** — the **durable** pause. A gated
   call is not run; the loop finishes the rest of the turn, emits `ApprovalRequired`, and
   stops. The pause is a fact in the log, so `resume(answers)` can arrive minutes later,
   from any client, after a disconnect or restart. `resume` reconstructs the pending set
   from the `ApprovalRequired` log event (so it survives restart and honors before-hook
   rewrites), then Approve → run, Deny → stop, free text → redirect the model.

**Dispatch order per call:** bad-args feedback → `before_tool_call` → confirm gate →
dispatch → `after_tool_call`.

**Confirm precedence:** `auto_approve` off → an explicit `confirm_tools` list wins if
set, else fall back to the tool's own `requires_confirmation` (so bash/edit/write gate
by default; client tools default to no-confirm unless listed).

## The HTTP boundary (`server/app.py`)

The uniform API every remote client speaks (see [api.md](api.md)). Two shapes on the
same `/run` endpoint: fire-and-forget (returns immediately; the run proceeds as a
background task — no pinned worker, survives a dropped client) or `?wait=true` (blocks
and returns a Flow-like terminal summary). `GET /stream?since=N` = replay-then-live.

### Security fences (in `SessionStore.create`, so every creation path is covered)

- **`ALLOWED_ROOTS`** — a session's `cwd` is realpath-resolved (defeating symlink/`..`
  escapes) and must sit under a configured root; else 400. Empty = unrestricted (dev).
- **`session_id`** must match `^[A-Za-z0-9_-]{1,64}$` — the id lands in on-disk
  filenames, so an unvalidated `../../etc/x` would be an arbitrary-file-write hole.

The daemon binds `127.0.0.1` by default and has no auth yet (loopback/dev only).

## End-to-end trace (one HTTP run)

```
flowd serve                 → create_app(SessionStore) → uvicorn
POST /sessions              → store.create() [cwd + session_id fences] → Session
POST /sessions/{id}/run     → background task: agent.run(session, msg)
  run   → publish RunStarted, append UserMessage → _loop
  _loop → _model_call: model.run() stream → publish TextDelta/AssistantMessage/Usage
        → append assistant → per tool_call: _handle_call
             before-hook → confirm? → _dispatch → Tool.__call__ → ToolResult → after-hook
        → pending? publish ApprovalRequired → RunEnded(paused)
          else next turn … → RunEnded(done)
  every publish → log.append() [seq + fsync] + fan out to subscribers + sink
GET /sessions/{id}/stream?since=N → replay log rows > N → attach live → until run_ended
POST /sessions/{id}/resume  → read ApprovalRequired from log → dispatch approved → _loop
```
