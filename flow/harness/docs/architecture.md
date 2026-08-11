# Architecture

The flow server is a standalone agent daemon: it runs model↔tool loops as durable,
disconnect-tolerant sessions and exposes them over HTTP/SSE and an embeddable Python
facade. Flow (Frappe) is one client among many.

## The shape

```
            ┌────────────┐   yields events / raises    ┌─────────────┐
 client ──▶ │  Session   │ ◀────────────────────────── │ agent loop  │
  HTTP      │ (lifecycle)│                             │ (pure gen)  │
  SSE       │  _commit ──┼──▶ log (JSONL)              └─────────────┘
  Agent     │            │──▶ transcript (reducer)            │
            │            │──▶ subscribers (live queues)   Model.run
            │            │──▶ event sink (Redis)         (retry envelope)
            └────────────┘                                    │
                                                        tools / client
                                                          callbacks
```

One rule everything else follows from: **the loop yields, the session commits.**

- `agent/loop.py` is a pure async generator. It asks the model, runs tools, and
  yields events; on failure it raises. It never persists, publishes, or retries.
- `session/session.py` owns the lifecycle. `Session._commit` is the **only writer**:
  append to the log (durable events get their `seq` here), fold into the transcript,
  fan out to live subscribers, forward to the optional sink. Everything a client can
  see went through this one door.

## Events

`events.py` is the shared contract. Durable events (`run_started`, `user_message`,
`assistant_message`, `tool_result`, `usage`, `approval_required`, `run_ended`,
`rewind`, `model_changed`, `compaction`, `run_error`) are appended to the per-session
JSONL log with a monotonic `seq` and rebuild all state on replay. Live-only events
(`text_delta`, `thinking_delta`, `tool_call_started`, `retry`, `compaction_started`,
`compaction_ended`) stream to subscribers and are never persisted — a missed
delta is healed by replaying the durable log.

Provider round-trip data (thinking signatures, Codex response items) rides in the
opaque `provider_state` field on content blocks — never encoded into ids or semantic
fields. User attachments are durable metadata blocks whose bytes live in a private
session attachment directory rather than bloating JSONL/SSE. Provider adapters resolve
those bytes at request time; unsupported images downgrade to an explicit text notice.

## State is derived, never stored

`session/transcript.py` is the one reducer. `Transcript.record(event)` folds each
committed event incrementally; `Transcript.replay(log)` is the single full read at
load. It maintains the provider-facing `messages`, the open tool-call batch, and
`pending_approval` as a field. There is no state machine on disk and no status column:

```python
RUNNING = the session's asyncio task is alive
PAUSED  = the transcript holds an undecided approval
IDLE    = otherwise
```

`missing_results()` closes a crashed run's open calls with stand-in `tool_result`
rows. Repairs are always committed **before** anything newer, so position alone
attaches them to their turn — no marker protocol.

## The log is a tree

Every durable row carries a `parent_seq`, and the **leaf** — the row the next event
will hang off — is the last row unless a `rewind` row moved it back to an earlier
entry. `Session.rewind(target_seq)` commits that marker (target `0` = the empty
root); the next run branches from the target, and the abandoned rows stay in the log,
off the active path (same design as pi and tau). Replay walks the parent chain from the leaf to the root and folds only
that path, so `messages`, `pending_approval`, and `missing_results` all describe the
active branch — rewinding away from a paused turn abandons its approval, and a dead
branch's open calls are never "repaired". The loop and the providers never know the
tree exists.

The model selection is a tree entry too: `Session.set_model` commits a
`model_changed` row (never during a run), and the effective selection — read by each
run at admission — is the last such row on the active branch, falling back to the
creation config. Config is immutable after create; a `run` request carries only its
message, and rewinding past a model change restores the previous selection.

## Compaction

Long sessions stay inside the model's context window by compaction: a summarization
call whose result is appended as a durable `compaction` row — never a rewrite. The row
carries the summary and `compact_up_to_seq`; the reducer folds it by swapping every
message at or before that boundary for one synthetic "Previous conversation summary"
user message, in place, because the running loop reads that exact list. The replaced
rows stay in the log and on the tree path, so `/entries` still serves the full history
and a rewind to before the compaction restores the uncompacted conversation.

`agent/compaction.py` owns the mechanics: a chars/4 estimator (the trigger prefers the
provider's own reported usage from the last turn), a boundary planner that keeps up
to the newest ~20k tokens—scaled down for small windows and large system/tool
prompts—and never splits a turn (the cut lands on a user message start, falling back
to an assistant start, never a tool result), and the summarizer — a
standalone tool-less model call whose deltas are consumed silently, and which updates
a previous summary instead of re-summarizing its prose. Its input is clipped per
message and budgeted to the model's window, so the giant tool result that caused an
overflow cannot make the recovery call overflow too. Three triggers:

- **threshold** — checked at the top of each turn, before the model call: past the
  window minus a reserve (or `compact_threshold_tokens`), the loop yields the
  protocol (`compaction_started` → `compaction` → `compaction_ended`); a failed
  attempt reports in-stream and never loses the turn.
- **overflow** — a `ProviderError(kind="context_overflow")` from the model call is
  recovered once per run: compact, retry the call once, and if that fails too the
  error settles as usual.
- **manual** — `Session.compact(instructions)` / `POST /sessions/{sid}/compact`
  replaces the whole conversation and runs as a normal operation (`run_started` …
  `run_ended`); 409 while running or paused. A `run` during it is a 409 too — the
  compaction never drains steering. Aborting it closes the pair
  (`compaction_ended(error_message="aborted")`) and ends with
  `run_ended(reason="aborted")`, with no fabricated assistant row.

`auto_compact: false` switches both automatic paths off. The summarization call is
internal and does not overwrite the provider usage retained for normal context
tracking.

## One operation at a time

`Session.run` / `Session.resume` admit one operation under `_operation_lock` and spawn
one task (`_drive`) that pulls the loop's events through `_commit`. A `run` against an
active session **steers**: the message queues and joins the run as its next turn. A
`run` against a paused session is a conflict — the approval must be resolved first
(`resume`) or abandoned (`cancel_pending`). `abort()` sets the per-operation abort
signal and discards undelivered steering.

When the loop raises instead of finishing its protocol, `_drive` settles the run in
one place (`_settle`): repair rows to close the interrupted turn, an aborted assistant
message if the turn never got one, a typed `run_error` for provider failures, then
`run_ended`. A session that reloads after a daemon crash performs the same repair in
its constructor.

## Providers own their failures

`model/base.py` defines the `Model` protocol — an async generator yielding deltas then
a terminal `AssistantMessage` + `Usage` — and `run_with_retries()`, the shared
envelope: bounded retries on transient/rate-limit errors honoring provider
`retry-after` hints, live `retry` events in-stream, cancellable backoff, and a
one-shot `refresh_auth` hook for rejected tokens. Adapters (`litellm.py`,
`providers/codex.py`) classify failures into the `ProviderError` taxonomy
(kind / retryable / status / detail). The agent loop contains no retry logic; a fix to
provider failure behavior lands in `model/`, never `agent/`.

Auth is resolved per run: `model/auth.py` prefers a stored credential (API key or
OAuth with single-flight refresh under an async lock), falls back to the provider's
environment variables, and hands `get_model` the runtime auth plus the refresh hook.

## Approval and interception

Two independent layers around every tool call, in order: bad-args feedback →
`before_tool_call` hook → confirm gate → dispatch → `after_tool_call` hook.

- **Hooks** are in-process callables (rewrite args, short-circuit, rewrite results);
  they are never persisted and exist only for embedded callers.
- **The confirm gate** is the durable pause. A gated call ends the turn with
  `approval_required` + `run_ended(paused)`; the pending batch lives in the log, so
  `resume` can arrive later, from any client, after a restart. `auto_approve` disables
  the gate; `confirm_tools` *adds* gates on top of each tool's own default.

## The boundary

`server/app.py` holds thin handlers over the Session verbs; a `SessionConflict` or
`ResumeError` anywhere answers HTTP 409 via one exception handler. SSE **is**
`Session.events(since)` — replay from a cursor, then the live feed, deduplicated by
`seq` — with the wire layer only deciding when to hang up. `agent/agent.py` is the
same engine for embedders: subscribe, submit, yield until `run_ended`.

`session/store.py` is disk only: private directories, meta persistence, the
session-id slug check, and the realpath cwd fence under `FLOW_ALLOWED_ROOTS`,
enforced in `create` and re-checked on `get` so every path in is fenced. Session
artifacts are grouped under `sessions/<project-name>--<path-hash>/`; each group
contains its sessions' JSONL logs, metadata, and attachment directories. The hash
keeps same-named projects distinct.

## Dependency direction

`loop` imports transcript/events/model/tools; `session` imports loop; `server`, `cli`,
and `agent.py` import session. Nothing under `model/` or `tools/` knows sessions
exist.

Layer ownership for fixes (the guardrails, abridged): the loop never persists or
publishes; provider failures live in `model/`; any new "what is the current state"
question extends `Transcript.record` — a new full-log scan is wrong by definition;
repairs precede newer entries; provider data goes in `provider_state`. The full
guardrails and the rebuild history live in [rebuild.md](rebuild.md).
