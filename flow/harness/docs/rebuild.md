# Rebuild charter

flow_server's behavior is right; its structure is not. The codebase grew by patching:
`agent/loop.py` was born at 385 lines and doubled through nine fix PRs, each solving a
real problem (the problems pi and tau also solve) by grafting code onto a structure that
could not absorb it. This document is the contract for rebuilding it — same behavior,
same wire contract, roughly half the code — as a sequence of reviewable PRs.

The rebuild starts from a bare package: the branch keeps only the project scaffolding
(pyproject, lockfile, CI, lint/type configs) and this charter; the old implementation
and its 219 tests live on `main` as the reference. Each PR adds one complete layer with
its tests, so the suite is always green for everything built so far. Files marked
"ported" are copied from `main` (reviewable by diffing against it); the old tests are
the behavior spec — scenarios are ported, not test code.

File references below describe the pre-rebuild tree as preserved on `main`; they are
the evidence, not live pointers.

## Root causes being fixed

1. **The loop pushes events** (`session.publish`) instead of yielding them. Everything
   downstream fights this: `Agent._drive` races a queue against the run task,
   `server._stream_events` re-implements the same push→pull conversion, `_model_call`
   hand-buffers durable events to fake transactionality, and `_run_with_lifecycle`
   converts exceptions into published terminal events through 65 lines of collected
   failures and re-raised cancellations.
2. **Retries and auth refresh live in the agent loop** (`_model_call`, 120 lines;
   `refresh_provider_model` closure mutating `nonlocal` state). They belong inside the
   provider adapter, emitting retry events in-stream (tau's shape).
3. **Session state is recomputed by re-scanning the log** with four different state
   machines (`_rebuild_messages`, `interrupted_tool_repairs`, `pending_approval`,
   server `_summary`), held together by the `details["transcript_repair"]` marker
   protocol. One incremental reducer replaces all of them.
4. **Run lifecycle is split across four files**: admission in `server/app.py` (calling
   the private `Session._start_operation`), the state machine in `session/store.py`,
   terminal events in `agent/loop.py`, and a second embedded driver in
   `agent/agent.py`.
5. **Cancellation is an ambient flag checked 21 times** in one file, with aborted
   assistant messages synthesized in three places.
6. **Provider round-trip state is smuggled** through neutral fields: codex stores raw
   reasoning items in `thinking_signature`, a versioned JSON micro-format in
   `text_signature`, and composite `call_id|item_id` tool-call ids.
7. **Concern scatter**: `store.py` mixes four concerns; "get an authenticated model"
   spans five files; `run` is defined six ways.

## Target layout

```
src/flow_server/
  config.py                 daemon env config (unchanged)
  events.py                 shared event contract; content blocks gain provider_state
  path_policy.py            shared path fences (unchanged)
  session/
    log.py                  SessionLog — ported unchanged
    transcript.py           NEW: the one reducer (messages, open batch, pending
                            approval, missing-result repairs)
    session.py              SessionConfig + Session — THE lifecycle owner:
                            run/resume/abort/cancel_pending, _commit (the only
                            writer), events(since)
    store.py                SessionStore only: disk layout, create/get, meta, cwd fence
  agent/
    loop.py                 pure async generator (~250 lines); yields events, raises
                            on failure; never persists, publishes, or retries
    client_tools.py         httpx callback dispatch + client confirm prompts
    agent.py                embedded facade — a thin alias over Session (~25 lines)
  model/
    base.py                 Model protocol, ModelRequest, cancellation utils,
                            retrying() wrapper shared by adapters
    litellm.py              LiteLLM adapter + OpenAI-message translation
    mock.py                 keyless deterministic model
    errors.py               provider failure classification
    credentials.py          0600 atomic credential store (unchanged)
    auth.py                 OAuth core + request-time resolution (merges old
                            auth.py + resolver.py)
    catalog.py              provider specs (unchanged)
    providers/
      codex.py              Codex auth provider + Responses wire, via provider_state
      opencode.py           OpenCode Go routing (unchanged)
  tools/                    ported verbatim (tool.py + builtins/)
  server/
    app.py                  thin handlers over Session verbs; wire contract unchanged
  cli/
    main.py                 flowd serve
    login.py                provider login/logout/status (renamed from cli/auth.py)
```

**Dependency direction** (import rule, enforced in review): `loop` imports
transcript/events/model/tools; `session` imports loop; `server`, `cli`, and `agent.py`
import session. Nothing under `model/` or `tools/` knows sessions exist.

## Guardrails

Every future fix names the layer it belongs to before it lands. Concretely:

1. The loop never persists, publishes, or converts exceptions into events — it yields
   and raises. `Session._commit` is the only place that appends to the log and fans out
   to subscribers and sinks.
2. Retries, token refresh, and aborted-message synthesis live inside `Model.run`
   (via `retrying()` in `model/base.py`). A fix touching provider failure behavior
   lands in `model/`, never `agent/`.
3. One reducer. Any "what is the current state" question is answered by extending
   `Transcript.apply`. A PR adding a new full-log scan is wrong by definition.
4. Repairs are appended before any new transcript entries, so position is the only
   ordering mechanism. Nothing writes positional markers into event payloads.
5. Provider round-trip data goes in `provider_state` — never encoded into semantic
   fields, ids, or signatures.
6. A fix adding more than ~30 lines to `loop.py` or `session.py` must first answer
   "which layer owns this?" in its PR description.
7. No migration code. flow_server has not shipped, so there are no logs, credentials,
   or clients in the wild to be compatible with: no upgrade-on-read shims, no legacy
   field handling, no format version negotiation. Schemas are written as they should
   be. (The cross-repo wire contract with Flow is not migration — see inventory 15.)

## Behavior inventory (must survive; parity-audited in PR 7)

The existing tests are the spec — port scenarios, not test code. Nothing here regresses:

1. Append-only seq-numbered JSONL: fsync, partial-append rollback, corruption located
   by line/offset.
2. Replay + live SSE with `since` cursor; `?wait=true` blocking summary on the same
   endpoint; steering while running.
3. Durable approval pause/resume across disconnect and restart: answers validated
   against the exact batch, stale `approval_seq` rejected, Deny halts, free text
   redirects, abandoned batches answered on abort (`cancel_pending`).
4. Interrupted-run transcript repair so providers accept a crashed session's history.
5. Abort at any await point, including of a paused session; aborted turns leave a
   provider-acceptable transcript.
6. Truncated turns (`length`): tool calls are never executed, errors fed back.
7. Provider error taxonomy (kind/retryable/status/detail/retry-after), bounded retries
   honoring provider hints, one-shot auth refresh on a rejected token.
8. Thinking blocks: ordered content, signatures preserved same-model, degraded to text
   cross-model, redacted handling.
9. Codex Responses wire (SSE events, reasoning round-trip, usage) and OAuth machinery
   (PKCE, single-flight refresh lock, 0600 atomic store, login CLI with loopback +
   manual fallback).
10. Security fences: session-id slug, realpath cwd/tool fences under
    `FLOW_SERVER_ALLOWED_ROOTS`, loopback-or-token bind guard, secrets never accepted
    as run inputs, redacted config echoes.
11. Tools: bash group-kill/timeout/truncation/spill, atomic multi-edit with diff,
    read paging, grep `--` fence.
12. Session meta persistence; per-run model/credential override that sticks.
13. Client tools over `callback_url` + `X-Harness-Token`, client-supplied confirm
    prompts, Frappe `{"message": ...}` envelope unwrapping.
14. Live deltas never persisted; the durable log heals any gap.
15. Wire contract with Flow and other clients: HTTP endpoints and payload shapes,
    Redis channel `harness:<sid>`, `X-Harness-Token`. These are cross-repo agreements,
    not back-compatibility — pre-rebuild session directories are disposable
    (guardrail 7).

## PR sequence

One layer per PR, bottom-up, so every PR's dependencies already exist and its tests
run against the real thing. The client-facing wire contract is proven at the edge: the
old HTTP assertions pass unmodified in PR 6.

- **PR 0 — charter + bare package** (this PR). This document; strip the branch to
  scaffolding (pyproject, uv.lock, CI, pre-commit, pyright, .gitignore), a bare
  `src/flow_server/__init__.py`, and a package smoke test so CI stays green.
- **PR 1 — events + log + transcript.** Fresh `events.py` with `provider_state` on
  `TextContent`/`ThinkingContent`/`ToolCall` and a single live-only
  `Retry(status=scheduled|started|exhausted)` event from day one. `session/log.py`
  ported verbatim. New `session/transcript.py`: `apply`, `fold`, `missing_results`,
  `pending_approval` as a field, results placed by position alone. Verify: reducer
  unit tests (batch ordering, first-result-wins, approval scoping across runs,
  `apply` == `fold`); ported log scenarios (fsync rollback, corruption line/offset,
  monotonic seq).
- **PR 2 — model core.** `model/base.py` (Model protocol, `ModelRequest`,
  cancellation utils, `retrying()` emitting `Retry` in-stream with cancellable
  backoff, retry-after, bounded attempts, one-shot refresh hook, aborted-assistant
  helper), `model/litellm.py` (translation ported from `main`'s `model.py`,
  thinking-block handling intact), `model/mock.py`, `model/errors.py`. Verify:
  ported model/translation/error scenarios plus retry/refresh scenarios — these are
  model-layer tests now.
- **PR 3 — auth + providers.** `config.py` (needed for credential paths),
  `model/credentials.py` + `model/catalog.py` ported, `model/auth.py` (OAuth core +
  request-time resolution; merges old `auth.py` + `resolver.py`),
  `model/providers/codex.py` (auth provider + Responses wire, round-tripping via
  `provider_state` — no `text_signature` micro-format, no `call_id|item_id`),
  `model/providers/opencode.py` ported. Verify: ported offline auth tests; codex
  wire tests rewritten against `provider_state`.
- **PR 4 — tools.** `path_policy.py`, `tools/tool.py`, `tools/builtins/` and their
  tests, all ported verbatim from `main` (review = diff against `main`). Verify:
  ported tool suite green.
- **PR 5 — loop + session + agent.** The heart. `agent/loop.py` pure generator
  (`run`/`resume` sharing one core; bad-args feedback → before-hook → confirm gate
  yielding `ApprovalRequired` → dispatch → after-hook; steering via callable;
  truncated-turn rule), `agent/client_tools.py`, `session/session.py`
  (`SessionConfig` + `Session`: `_admit`, `_commit` as the only writer, exception
  settlement in one ~15-line place, `run`/`resume`/`abort`/`cancel_pending`,
  `events(since)`), `session/store.py` (disk only), `agent/agent.py` as a thin
  passthrough. Verify: all agent-loop/session scenarios ported (approval batches,
  deny halts, redirect, stale `approval_seq`, steering, abort-while-paused,
  truncated turns, hook order, crash repair); `loop.py` ≤ ~250 lines and imports
  neither httpx nor the log; grep finds no `session.publish`.
- **PR 6 — server + CLI.** `server/app.py` with ~5-line handlers over Session verbs;
  SSE = `session.events(since)`; `?wait=true` drains the run generator;
  `cli/main.py` + `cli/login.py`. Verify: wire assertions ported unmodified from
  `main`'s `test_server` (the contract proof), including reconnect-with-`since` over
  the live `/stream` path.
- **PR 7 — parity audit + docs.** Walk the behavior inventory above and list any
  intentionally changed behavior (target: none); rewrite `docs/`
  (architecture/api/tools/authentication/development) for the new tree; drop the
  PR 0 smoke test; pyright + ruff + CI green.

## After the rebuild

- **Backpressure** becomes a bounded-queue + detach policy inside `Session._commit`,
  the single fan-out point (slow subscribers detach and heal via replay).
- **Context compaction** becomes a durable `Compaction` event folded through
  `Transcript.apply` — never a rewrite of the log.
