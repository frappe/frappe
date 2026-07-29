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
| `AssistantMessage` | ✓ | ordered text/thinking/tool-call blocks, provider identity, and model stop reason |
| `ToolResult` | ✓ | a tool's outcome (`content` seen by the model; `details` for rendering; `is_error`) |
| `Usage` | ✓ | token/cost accounting for a turn |
| `ApprovalRequired` | ✓ | the run paused; `calls` = `PendingCall`s awaiting a decision |
| `RunEnded` | ✓ | terminal; `reason` ∈ done/length/max_turns/budget/aborted/error/paused |
| `RunError` | ✓ | a run-level failure; provider failures include typed kind/status/retryability/detail |
| `TextDelta` | — | a streamed text chunk |
| `ThinkingDelta` | — | a streamed reasoning chunk |
| `ToolCallStarted` | — | a tool call's name became known mid-stream |
| `RetryScheduled` | — | the next provider attempt, its place in the attempt budget, and the cancellable delay |
| `RetryStarted` | — | a scheduled provider attempt has begun; discard the turn's streamed text |
| `RetryExhausted` | — | no further provider attempt will be made |

`content` on a `ToolResult` is what the model sees; `details` (diff, truncation,
exit code, …) rides the durable stream for rich rendering but is **never** sent to the
model.

An `AssistantMessage.content` list preserves provider order. Its blocks are
`text` (`text`, optional `text_signature`), `thinking` (`thinking`, optional
`thinking_signature`, `redacted`), or `tool_call` (`id`, `name`, `arguments`). The
message also records `api`, `provider`, `model`,
`response_model`, `response_id`, and `stop_reason` (`stop`, `length`, `tool_use`,
`error`, or `aborted`). `text`, `thinking_text`, and `tool_calls` remain Python
convenience properties; they are not second persisted representations.

## The durable log (`session/log.py`)

An append-only JSONL file, one per session. `append()` assigns the next `seq`, writes,
and `fsync`s. `read_since(n)` returns every entry with `seq > n` — this is both the
**replay** path (catch a reconnecting client up) and the **restart** path (rebuild
state from disk). Durability lives here and nowhere else.

Loading is strict and line-aware: malformed JSON, invalid event shapes, live-only
events, and non-monotonic sequences fail with the file and line number. Flow does not
guess past or truncate a corrupt tail; Pi and Tau likewise reject invalid JSONL rather
than silently discarding history. Appends are serialized within one `SessionLog`, and
the sequence advances only after a complete line is written.

If execution stops after an `AssistantMessage` has been persisted but before every
tool call has a `ToolResult`, Flow appends synthetic error results before the
transcript is used again. Each repair records the originating assistant sequence so
replay can place it in source-call order without rewriting the append-only log.
Unresolved calls in a durable approval pause are deliberately excluded: they are
pending work, not interrupted work.

## Session & config (`session/store.py`)

- **`SessionConfig`** (a Pydantic model, sent per-session by any client) is the whole
  extensibility seam: `model`, `system_prompt`, `tools`, `client_tools`, `callback_url`,
  `confirm_tools`, `auto_approve`, `cwd`, `max_turns`, `max_output_tokens`, `stream`, …
- **`Session`** holds the live transcript (`messages`, rebuilt from the log via
  `_rebuild_messages`), an `abort` event, a `steer_queue`, and the pub/sub. `publish()`
  is the fan-out: persist-if-durable → deliver to live subscribers → forward to an
  optional sink (e.g. Redis). It also owns interrupted-transcript repair so both live
  failures and cold session loads use the same durable rule.
- **`SessionStore`** owns create/get and enforces the security fences (below).

## The model layer (`model/`)

`Model.run(messages, tools, *, system_prompt, stream)` is an **async generator** over
the provider-neutral typed transcript: streaming yields `TextDelta`, `ThinkingDelta`
and `ToolCallStarted`, and every turn ends with a terminal `AssistantMessage` then a
`Usage`. Each adapter converts the canonical transcript to its provider wire format at
the boundary.

Opaque reasoning signatures are replayed only when `api`, `provider`, and requested
`model` all match. On a model change, non-redacted visible thinking degrades to plain
text and opaque/redacted state is dropped. This follows Pi's cross-model safety rule;
it is intentionally stricter than blindly forwarding a provider blob.
`thinking_signature` contains only opaque provider continuation data, never the name of
a provider wire field. Codex text signatures encode versioned output-item identity and
an optional response phase. On the LiteLLM path signatures live in `thinking_blocks`
(Anthropic-family) — the only channel those providers read on the way back in, and the
one whose absence makes LiteLLM silently drop the `thinking` parameter. A signature
also terminates its block: the next reasoning fragment opens a new one. Unsigned
thinking is never replayed as a block, since the provider cannot verify it.

Before model construction, `resolve_model_auth()` selects a stored provider credential,
falling back to the provider's standard environment variable. `get_model(name)` then
dispatches on the model prefix:
the keyless `mock` and native subscription `codex` providers have dedicated models;
everything else falls through to `LiteLLMModel`.

The credential store is user-global and type-tagged (`api_key` or `oauth`). Session
metadata contains only an optional `credential_id`. Provider secrets, headers, and base
URLs are resolved internally and cannot be supplied through session or run payloads.

Provider adapters normalize HTTP, SDK, streaming, and transport failures into
`ProviderError`. Its `kind` distinguishes rate limiting, overload, timeout,
authentication, context overflow, invalid request, transport, and unknown failures.
The LiteLLM adapter maps LiteLLM's provider-neutral exception classes first and uses
status/message inspection only as a fallback for unexpected exceptions; native
adapters such as Codex classify their own HTTP and streaming protocol errors.
The loop retries only retryable failures from the current model call, never a whole
agent turn: completed tools therefore cannot run twice. Flow makes at most two
transient retries (three attempts on the normal path), using bounded exponential
backoff with jitter and honouring a provider's own retry header. A provider asking to
be retried more than a minute out is treated as terminal instead of slept on, so one
throttled call cannot stall a run and spend the whole budget waiting. Backoff is
cancellation-aware. Ordinary authentication and invalid requests are not retried; an
explicitly expired OAuth token gets one separate refresh/re-resolution attempt, and any
failure of that refresh — a rejected token or a fault reaching the token endpoint —
ends the run as a typed authentication error rather than escaping untyped.

Durable terminal model events are buffered until an attempt succeeds, so a failed
attempt cannot leave a duplicate durable assistant message or usage record. Its live
deltas are already out, though, and the retried attempt restreams the turn from the
start: **`RetryStarted` is the point at which a client drops the in-flight turn's
streamed text.** `RetryScheduled` and `RetryExhausted` bracket that lifecycle and are
published only when an attempt was really scheduled, so a failure that was never
retried emits none of the three. Exhaustion commits one failed assistant response and
one typed `RunError` lifecycle. Context overflow is non-retryable and ends through that
same clean error lifecycle; Flow does not compact history yet.

## The agent loop (`agent/loop.py`) — the heart

`run()` → publish `RunStarted`, append the user message, enter `_loop`. Each turn:

1. **`_model_call`** — build a provider-neutral `ModelRequest` from the transcript,
   tools, system prompt, stream settings, and the active cancellation signal;
   consume `model.run()`, publish deltas + `AssistantMessage` + `Usage`, and return the
   assistant + token count.
2. append the assistant message. If it has no tool calls → `RunEnded(done)`.
3. for each tool call, **`_handle_call`** (dispatch order below).
4. if any call was confirm-gated → publish `ApprovalRequired`, stop with `paused`.
5. else check caps (`max_turns`, `max_output_tokens`, `abort`) and loop.

One outer lifecycle boundary covers setup, model streaming, hooks, tool dispatch, and
resume continuations. It repairs interrupted tool batches, publishes one `RunError`
for operational failures, and attempts exactly one terminal `RunEnded`. The session
task clears runtime state in `finally`, including when terminal-event persistence
itself fails.

Cancellation is raced across every async boundary rather than polled only between
turns. The model iterator is closed (which closes native provider HTTP streams), tool
and callback tasks are cancelled, and hooks are checked immediately before and after
they run. Short synchronous filesystem operations cannot be interrupted halfway
through; the checks on both sides prevent later work from starting. Bash additionally
kills its whole process group when its tool coroutine is cancelled. Cancellation is a
terminal outcome, never an operational error or retry: an aborted assistant message is
persisted, unfinished tool calls are repaired with error results, and exactly one
`RunEnded(aborted)` closes the operation.

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

Each session has one runtime `SessionState` (`idle`, `running`, or `paused`), one
operation lock, and at most one registered task. Admission changes the state and
registers the task before the loop can run. Both HTTP modes use that same task:
`wait=true` awaits it, while the default response leaves it running. Cleanup happens
in `finally`, deriving `paused` from the latest unresolved durable approval batch and
otherwise returning to `idle`.

An overlapping `/run` is accepted only as explicit steering. Other overlaps are
rejected. A resume must carry the current approval event's `seq` and an exact answer
set, preventing a delayed or duplicated client request from resolving a different
batch. Unlike Pi/Tau's in-process confirmation UI, this durable paused state is a
Flow-specific server extension needed for disconnect/restart-safe approval.

Flow currently has one active-run queue: steering. `/abort` sets the operation signal
before clearing that queue, and `steer()` rejects additions after the signal is set.
There is no separate follow-up queue; if one is added later it must follow the same
explicit cancellation policy rather than leaking messages into the next run.

`flowd serve` runs one application worker. The operation lock and JSONL append lock are
in-process guarantees; multiple daemon processes must not share the same session
directory without an external single-writer coordinator.

### Security policies

- **`ALLOWED_ROOTS`** — a session's `cwd` and every path passed to `read_file`, `write`,
  `edit`, or `grep` are realpath-resolved (defeating normal symlink/`..` escapes) and
  must sit under a configured root. The configured roots themselves are `~`-expanded;
  addressed paths are not. Stored sessions are revalidated when loaded.
  Empty = unrestricted (dev).
- **`session_id`** must match `^[A-Za-z0-9_-]{1,64}$` — the id lands in on-disk
  filenames, so an unvalidated `../../etc/x` would be an arbitrary-file-write hole.

`ALLOWED_ROOTS` is not an OS sandbox: `bash` runs with the daemon process's filesystem
permissions and can access paths outside those roots. Deployments that need containment
must isolate shell execution in a container or equivalent sandbox.

The daemon binds `127.0.0.1` by default. When `FLOW_SERVER_AUTH_TOKEN` is set, all
endpoints except `/healthz` require a matching bearer token. `flowd serve` refuses to
bind a non-loopback host without that token. Session metadata and logs are written
`0600`; provider credentials use an atomic, locked `0600` store.

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
POST /sessions/{id}/resume  → match approval seq + exact ids → dispatch approved → _loop
```
