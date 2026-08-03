# Flow TUI — phased implementation plan

## Context

`flow` is a durable agent daemon: FastAPI + SSE server, tree-shaped session log, typed
pydantic event contract (`src/flow/events.py`). Today bare `flow` runs the server in the
foreground and there is no client UI. `docs/development.md` (Part 2) already plans the
target surface: bare `flow` starts a private daemon on an ephemeral port and attaches a
TUI; `flow serve` runs the daemon in the background; `flow attach` connects to a running
daemon.

This plan builds that TUI on textual (which bundles rich) as a separate top-level package
`src/flow_tui`, with its own HTTP/SSE client — no client code lands in `src/flow`. A future
Vue web shell reuses the server-side contracts (events, endpoints, prompt builder), not the
Python client. Decisions already made with the user:

1. The bare-`flow` private daemon dies when its TUI exits. Quit during an active run
   aborts and drains without a confirmation prompt.
2. Model catalog lives server-side: new `GET /models` endpoint, derived from
   `litellm.model_cost` and filtered to providers that are actually configured
   (credential stored or env key set). Picker also accepts free text.
3. Reasoning effort gets full server plumbing (SessionConfig → LoopInputs →
   `get_model(params=...)`). Default is `None` = provider default (no effort param sent).
4. System prompt building is a shared job. The SERVER owns a sectioned builder:
   default pi-style coding-agent preamble → `$HOME/AGENTS.md` → project `AGENTS.md`
   (from session cwd, walking up to the git root) → client-injected appendix. Clients
   inject via new `SessionConfig` fields: `system_preamble` (replaces the default
   preamble) and `system_suffix` (appended after all sections). `system_prompt` stays
   as a verbatim full override (escape hatch; skips composition entirely).
   AGENTS.md only — no CLAUDE.md fallback. `~/.agents/` skills are deferred entirely.
5. `auto_approve=True` is the DEFAULT session behavior, not a stopgap. The approvals UI
   still exists for sessions with confirmation enabled (`--confirm` flag); guardrails
   come later.
6. Session continuity: bare `flow` starts fresh; `flow -c` continues the most recent
   session for the cwd; a `--resume` picker comes later. In-TUI live session switching
   (`/sessions`) stays in scope.
7. Idle streaming: the server gains `?follow=true` so the SSE stream stays open between
   runs (keepalive comment every 15 s) — no idle reconnect polling.
8. Mid-run Enter steers (server semantics, with a "steered" marker); a keybind
   (alt+enter) queues the message client-side for after `run_ended` instead.
9. Accepted risk: two daemons opening the same session file (`flow -c` from two
   terminals) can corrupt the log. Documented, not prevented. Future fix: per-session
   `flock`.
10. POSIX-only for now.

Ground truths that shape the plan (verified in code):

- `bash` has `requires_confirmation=True`, but sessions default to `auto_approve=True`
  (decision 5) so the default path never pauses; the approvals UI serves `--confirm` sessions.
- `get_model()` already accepts `params` (`src/flow/model/__init__.py:38`) and `LiteLLMModel`
  splats it into the request; `loop._authenticated_model()` (`src/flow/agent/loop.py:314`)
  just never passes it. Effort is wiring, not new machinery.
- SSE stream closes at the end of every run; clients must reconnect with
  `since=<last durable seq>`. `Session.events()` dedups by seq.
- Live-only events (`text_delta`, `thinking_delta`, `tool_call_started`, `retry`) are previews;
  the durable `assistant_message` replaces them. `retry(status="started")` discards prior deltas.
- No `GET /sessions` list endpoint and no model catalog exist today.
- Tests: `TestClient` over `create_app` for REST; real uvicorn on port 0 for live SSE;
  `monkeypatch flow.agent.loop.get_model` + `MockModel`. Style: tabs, double quotes, line 110.

## Module layout

```
src/flow/                 # server package — no TUI/client code
  session/prompt.py       # NEW: sectioned system-prompt builder + AGENTS.md discovery
  cli/
    daemon.py             # spawn/readiness/teardown for private + background daemons
    main.py               # reshaped: flow / serve / attach / login / logout / providers
src/flow_tui/             # TUI package (same distribution, second top-level package)
  client/                 # HTTP/SSE client — lives here, NOT in flow
    api.py                # FlowClient: async httpx wrapper over the HTTP API
    stream.py             # SSE parser + reconnecting EventStream with since-cursor
    state.py              # ConversationState reducer (pure, no I/O)
  app.py                  # FlowApp(App)
  controller.py           # FlowClient + EventStream + ConversationState → widget updates
  commands.py             # command registry (slash + palette share it)
  screens/pickers.py      # ModelPicker, EffortPicker (ModalScreen)
  widgets/
    conversation.py       # VerticalScroll of per-message widgets
    messages.py           # UserMessageView, AssistantMessageView, ThinkingBlock, ToolCallView
    approval.py           # inline approval card
    composer.py           # TextArea input, slash dispatch, editor hook
    status_bar.py
  styles.tcss
```

Dependency direction: `flow_tui` imports `flow` (events models, `SessionConfig`) — never
the reverse. The `flow` console script stays at `flow.cli.main`; the TUI code path does a
lazy `import flow_tui` so the server package has no hard import of textual. Packaging:
`pyproject.toml` `packages = ["src/flow", "src/flow_tui"]`.

Each phase is one PR-sized commit with tests. Phases 1, 2, and 5 are server-only; 3–4 are
the client core in `flow_tui`; 6–10 build the TUI against a manually run `flow serve`;
11 lands daemon lifecycle; 12 is isolated polish.

---

## Phase 1 — Server: `GET /models` and `GET /sessions`

**Files:** `src/flow/model/catalog.py`, `src/flow/server/app.py`, `src/flow/session/store.py`, tests.

- Derive the catalog from `litellm.model_cost` at runtime — no curated list to maintain.
  Filter: provider is configured (see next point), `mode == "chat"`, and
  `supports_function_calling` (the agent loop needs tools). Map keys to flow model names
  (provider prefix). Add native providers (`codex/...`) from their own known ids.
- Factor the credential-availability predicate out of `login.show_providers`
  (`src/flow/cli/login.py:62`) so login and the endpoint share it. Only configured
  providers appear in the payload; free text in the picker covers everything else.
- `GET /models` → `{"models": [{"name", "provider"}]}`.
- `SessionStore.list()` reads `*.meta.json` cheaply (no log replay); `GET /sessions` →
  `[{session_id, state, model, latest_seq, cwd}]`.

**Test:** TestClient; models with/without credentials (tmp CredentialStore + env monkeypatch),
assert non-chat litellm entries are excluded; session list including a cold on-disk session
(new store over the same dir).

## Phase 2 — Server: reasoning-effort plumbing

**Files:** `src/flow/session/config.py`, `src/flow/events.py` (`ModelChanged`),
`src/flow/session/session.py`, `src/flow/server/app.py`, `src/flow/agent/loop.py`,
new `src/flow/model/reasoning.py`.

- `SessionConfig.reasoning_effort` on pi's ladder:
  `Literal["off","minimal","low","medium","high","xhigh","max"] | None = None`.
- `ModelChanged.reasoning_effort` (durable, per-branch, survives rewind); `set_model` and
  `SetModelRequest` accept it; expose current value in `GET /sessions/{sid}`.
- `LoopInputs.reasoning_effort`; `_authenticated_model` passes
  `params=reasoning_params(inputs.model_name, effort)`.
- `reasoning.py: reasoning_params(model, effort) -> dict | None` (pi's mappings):
  - `anthropic/*` → thinking budget `{minimal: 1024, low: 2048, medium: 8192, high: 16384}`
    (xhigh/max clamp to high); `"off"` → `{"thinking": {"type": "disabled"}}`.
  - litellm path (openai, gemini, xai, …) → `{"reasoning_effort": effort}` (litellm unified
    param); `"off"` omits the parameter.
  - `codex/*` → `{"reasoning": {"effort": effort, "summary": "auto"}}`; `"off"` omits it.
    `providers/codex.py` already splats `params` into the Responses payload.
- Old `ModelChanged` rows replay fine (pydantic default None).

**Risk:** Anthropic `thinking` needs `max_tokens` headroom — verify against `LiteLLMModel`
request assembly; `budget_tokens` must be below max output tokens.

**Test:** unit-test `reasoning_params`; loop test with monkeypatched `get_model` capturing
`params`; server test: create with effort → change via `/model` → rewind restores prior effort.

## Phase 3 — Client core: `FlowClient` + reconnecting `EventStream`

**Files:** new `src/flow_tui/client/{api,stream}.py`, `tests/test_client.py`;
`pyproject.toml` (add `src/flow_tui` to packages).

- Async httpx (Textual is asyncio; sync would force threads). `FlowClient(base_url, token=None)`
  with typed methods for every endpoint. Reuse `flow.events.parse_event` and `SessionConfig`
  directly — no parallel shapes.
- **Server change (small):** `GET /stream?follow=true` keeps the SSE connection open when
  the session goes idle instead of closing at end of run. The generator stays subscribed
  and emits an SSE comment line (`: keepalive`) every 15 s so proxies and dead-peer
  detection work. Default (`follow` absent) keeps today's close-at-boundary behavior.
- `EventStream(client, sid, since=0)` async iterator: open `/stream?since=cursor&follow=true`,
  yield parsed events, advance cursor only on durable events with seq, drop `seq <= cursor`
  (reconnect races never double-render). Reconnect with backoff only on transport error or
  unexpected close. `stop()` closes cleanly.

**Test:** REST via `httpx.ASGITransport`; live stream via real uvicorn on port 0
(existing pattern in `tests/test_server.py`): two runs with MockModel over ONE follow
connection, assert each durable event yielded exactly once and keepalives are ignored;
kill the connection mid-run, assert reconnect resumes from cursor without duplicates.

## Phase 4 — Client core: `ConversationState` reducer

**Files:** new `src/flow_tui/client/state.py`, `tests/test_client_state.py`.

- `apply(event) -> list[Change]` (typed notices: `EntryAdded`, `EntryReplaced`, `StreamDelta`,
  `StatusChanged`, …) so the TUI updates incrementally.
- State: durable `entries` (active path), `partial` (accumulated deltas + started tool calls,
  arrival order), `pending_approval` (+ seq), `running`, model/credential/effort (folded from
  `model_changed`, seeded from `GET /sessions/{sid}`), usage totals, `last_error`, `retry`.
- Rules per wire contract: `assistant_message` drops `partial` and appends;
  `retry(started)` clears `partial`; `approval_required` sets pending, cleared by matching
  `tool_result` / `run_started` / `run_ended`; `rewind` truncates entries to `seq <= target`
  and refolds model/effort; `run_started` clears `last_error` and `retry`.

**Test:** pure unit tests, scripted sequences: delta replacement, retry discard, approval
lifecycle, rewind truncation + refold, usage accumulation, steering mid-run.

## Phase 5 — Server: sectioned system-prompt builder

**Files:** new `src/flow/session/prompt.py`; `src/flow/session/config.py`,
`src/flow/session/store.py` (compose at session create); `docs/api.md`;
`tests/test_system_prompt.py`.

- New `SessionConfig` fields, all optional:
  - `system_preamble: str | None` — replaces the default preamble section.
  - `system_suffix: str | None` — appended after all sections (the client-injection point).
  - `system_prompt: str | None` — semantics change: when set, used VERBATIM and
    composition is skipped (escape hatch, keeps existing tests/embedders working).
    Its default stops being `"You are a helpful agent."` and becomes None → compose.
- `build_system_prompt(config, home=None) -> str` composes, in order, with provenance
  headers per section:
  1. Preamble: `system_preamble` or the default pi-style coding-agent prompt
     (module constant — direct, terse, tool-usage and safety guidance).
  2. `$HOME/AGENTS.md` if present (global instructions).
  3. Project `AGENTS.md`: walk up from `config.cwd`, stop at the git root (first ancestor
     with `.git`) or `$HOME`, whichever comes first; outermost-first so nearer files
     override by recency. AGENTS.md only — no CLAUDE.md fallback.
  4. `system_suffix` if set.
- Composition happens ONCE at session create (`SessionStore.create`); the resolved prompt
  is what the loop uses and what `GET /sessions/{sid}` reports. AGENTS.md edits do not
  leak into an existing session mid-conversation — config stays immutable, transcripts
  stay reproducible.
- `~/.agents/` skills stay out of scope (deferred).

**Test:** unit tests on `build_system_prompt` with tmp_path trees (nested AGENTS.md,
missing files, preamble override, suffix, verbatim escape hatch); `home` is a parameter so
no `Path.home` monkeypatching. Server test: create session → GET reports composed prompt.

## Phase 6 — TUI shell MVP (`flow attach --url` only)

**Files:** new `src/flow_tui/{app,controller}.py`,
`src/flow_tui/widgets/{conversation,messages,composer,status_bar}.py`, `styles.tcss`;
`pyproject.toml` (add `textual` to deps, `textual-dev` to dev); `src/flow/cli/main.py`
(add `attach` with required `--url`, lazy `import flow_tui`; new session by default via
`POST /sessions` with `cwd=os.getcwd()` — the SERVER composes the prompt; the TUI passes
`system_suffix` for client-specific notes, e.g. UI conventions); `tests/test_tui_shell.py`.

- **Per-message widgets in `VerticalScroll`, not `RichLog`** — needed for delta updates
  in place, delta→durable replacement, collapsible thinking (phase 8), and interactive
  approval cards (phase 7). One widget per durable entry + one mutable `PartialAssistantView`
  at the tail, swapped when the durable message arrives. Anchor scroll to bottom unless the
  user scrolled up.
- Controller owns `FlowClient`, `EventStream` (Textual worker), `ConversationState`; widgets
  never touch httpx → pilot-testable with a fake controller.
- Composer: `TextArea`; Enter submits, `ctrl+j` inserts newline. Enter while running =
  steering (server answers `{"status":"steered"}`; show a marker); `alt+enter` while
  running queues the message client-side and sends it after `run_ended` (queued indicator
  in the status bar; queue survives stream reconnects — it lives in the controller, not
  the stream). One `ctrl+c`/Escape aborts the run; second prompts quit.
- Status bar: model · effort · state · Σ tokens · cost · session id.
- Renders: user/assistant text, tool call one-liner + result preview, run_error banner,
  retry status ("retrying 2/5 in 3 s"). Thinking as plain dimmed text for now.
- Sessions are created with `auto_approve=True` — this is the permanent default (decision 5),
  not a stopgap. A `--confirm` flag creates gated sessions once phase 7 lands.

**Risk:** textual on Python 3.14 — verify import + `run_test()` as the first commit of this
phase; fall back to a newer textual pre-release if broken. Long-transcript reflow cost is
accepted for MVP (`entries?path=active` seeding + virtualization later).

**Test:** `App.run_test()` pilot with a fake controller: rendering, delta→durable swap,
steering, status bar. One integration pilot against real uvicorn + MockModel.

## Phase 7 — Approvals UI + pause/resume

**Files:** new `src/flow_tui/widgets/approval.py`; `controller.py`, `messages.py`; tests.

- On `pending_approval`: `ApprovalCard` per pending call at the log tail — prompt text,
  `[a]pprove [d]eny`, free-text input (free text = redirect per contract), "approve all"
  shortcut for batches. Submit → `POST resume {approval_seq, answers}`; card collapses into
  a verdict line. Bind `cancel_pending` for abandoning a paused run.
- Status bar shows `paused — awaiting approval`; composer disabled with a hint while paused.
- Add the `--confirm` flag: creates the session with `auto_approve=False` so tool gates
  actually fire. Default stays `auto_approve=True`.

**Test:** pilot drives `approval_required` → key presses → assert resume payload; integration
with MockModel scripting a bash call in a `--confirm` session → approve → run completes.

## Phase 8 — Thinking traces (collapsible) + tool-result rendering

**Files:** `src/flow_tui/widgets/messages.py` (add `ThinkingBlock` on textual `Collapsible`),
render helpers, `app.py` binding.

- Each `ThinkingContent` block → `Collapsible(title="thinking · n chars", collapsed=True)`,
  preserving block interleaving (content order is meaningful). `redacted=True` renders as a
  sealed marker, never expandable.
- `ctrl+t` global toggle: app-level reactive flips all thinking blocks. Live `thinking_delta`
  streams into the partial view's thinking block (dimmed), honoring the toggle.
- Tool results: dispatch on `tool_result.details` keys — diff → syntax highlight, exit
  code/truncation → badges, fallback → fenced preview in a Collapsible. Cover only the
  `details` shapes the builtin tools actually emit.

**Test:** pilot: interleaved thinking/text/tool message, collapsed by default, `ctrl+t`
toggles, redacted stays sealed; render assertions for a bash result and an edit diff.

## Phase 9 — Command registry, slash commands, palette

**Files:** new `src/flow_tui/commands.py`; `composer.py`, `app.py`; tests.

- `Command(name, description, run, arg_hint)` in a module registry with a `@command`
  decorator. Initial set: `/model`, `/effort`, `/abort`, `/rewind [seq]` (default: last user
  message), `/new`, `/sessions` (live switch: list via `GET /sessions`, pick one, controller
  tears down its EventStream and re-seeds ConversationState on the new sid), `/help`, `/quit`.
- Composer intercepts leading `/`; unknown command → inline error. Autocomplete deferred.
- Use textual's built-in `CommandPalette` with a custom `Provider` fuzzy-matching the same
  registry; bind explicitly to `ctrl+p`.

**Test:** registry parse/dispatch unit tests; pilot: `/abort` reaches controller; palette
opens and runs a command.

## Phase 10 — Model + effort pickers

**Files:** new `src/flow_tui/screens/pickers.py`; wire into `commands.py`; tests.

- `ModelPicker(ModalScreen)`: `Input` filter over `OptionList` fed by `GET /models`
  (configured providers only); Enter with no highlighted option submits the raw filter
  text (free-text path for anything the catalog missed). Result → `set_model`.
- `EffortPicker`: default (None — provider default, no param sent) plus pi's ladder
  off/minimal/low/medium/high/xhigh/max → `set_model(..., reasoning_effort=x)`.
- `set_model` mid-run returns 409 → status-bar toast. Status bar updates from the durable
  `model_changed` event, not optimistically.

**Test:** pilot with faked models payload: filter, select, free text, 409 toast.

## Phase 11 — Daemon lifecycle + CLI reshape

**Files:** new `src/flow/cli/daemon.py`; `src/flow/cli/main.py` (drop "bare flow = serve"
in `_with_default_command`); `docs/development.md`; `tests/test_daemon_lifecycle.py`.

- **Subprocess, not in-process:** uvicorn signals and Textual both want the main loop;
  subprocess dogfoods the same path as `flow serve`; a daemon crash becomes a recoverable
  UI state instead of killing the TUI.
- Spawn: `Popen([sys.executable, "-m", "flow.cli.main", "serve", "--foreground", "--port-file",
  path, "--parent-watch"], env={**os.environ, "FLOW_AUTH_TOKEN": secrets.token_urlsafe(32)},
  stdin=PIPE, stdout/stderr → log file under data dir)`. Ephemeral port: bind a socket with
  port 0 ourselves, write the port file, pass the socket via `uvicorn.Server.serve(sockets=[sock])`.
  Auth token always set for private daemons, even on loopback.
- Readiness: poll port file (≤5 s), then `GET /healthz` with token.
- Teardown: quit while a run is active aborts and drains WITHOUT a prompt — `POST /abort`,
  wait briefly (≤5 s) for `run_ended` so the log gets a clean aborted terminus, then
  `terminate()`, 3 s grace, `kill()`. Orphan safety even under SIGKILL of the TUI:
  `--parent-watch` spawns a thread in the child that blocks reading inherited stdin;
  EOF (parent died) → `os._exit(0)`.
- Crash handling: stream loop hits connection-refused and `proc.poll() is not None` → fatal
  modal with daemon log path; no auto-respawn (sessions are durable; rerun `flow`).
- CLI surface:
  - `flow` → spawn private daemon (data dir stays `FLOW_DATA_DIR` — daemon is ephemeral,
    session logs persist), create session, run TUI, teardown. `flow -c/--continue` reuses
    the most recent session whose `cwd` matches the current directory (via `GET /sessions`)
    instead of creating one; `--resume` (session picker at launch) is a later addition.
  - **Accepted risk:** two daemons can open the same session file (e.g. `flow -c` in two
    terminals) — two writers on one append-only log can corrupt it. Documented in
    `docs/development.md`; not prevented. Future mitigation: `fcntl.flock` per session file.
  - `flow serve` → background via `start_new_session=True`, print address, exit;
    `--foreground` keeps current behavior. POSIX-only for now (note in docs).
  - `flow attach [--url] [--session]` → default `http://{FLOW_HOST}:{FLOW_PORT}`, token from
    `FLOW_AUTH_TOKEN`; session picker over `GET /sessions`; starts nothing. Discovery of
    private ephemeral daemons stays out of scope by design.

**Test:** lifecycle without the TUI: spawn helper → healthz OK with token / 401 without;
terminate → gone; orphan test: close parent pipe end, child exits ≤2 s. Extend
`tests/test_cli.py` for parsing.

## Phase 12 — External editor (`ctrl+x ctrl+e`) + composer polish

**Files:** `src/flow_tui/widgets/composer.py`, `app.py`; tests.

- Chord: `ctrl+x` arms a one-key chord (1.5 s timer disarms), `ctrl+e` fires. Also a palette
  command ("Edit in $EDITOR") for discoverability.
- Flow: draft → `NamedTemporaryFile(suffix=".md")` → `with app.suspend():
  subprocess.run([*shlex.split(editor), path])` → read back into composer.
  `$VISUAL` else `$EDITOR` else disabled with hint.
- **Risk:** `app.suspend()` needs a real tty — guard with try/except + toast. Document that
  `$EDITOR` must block (e.g. `code -w`).

**Test:** unit-test `edit_text_via_editor(text) -> str` with a script editor
(`sh -c 'echo x >> "$1"'`) and a stubbed suspend context; pilot tests chord arming.

---

## Verification (end to end)

1. `uv run pytest` green after every phase; ruff + ty clean (tabs, line 110).
2. After phase 6: `uv run flow serve --foreground` in one terminal,
   `uv run flow attach --url http://127.0.0.1:8787` in another; converse with
   `FLOW_MODEL=mock`, then a real model.
3. After phase 7: in a `--confirm` session, run a prompt that triggers `bash`; approve,
   deny, and redirect paths. Default session runs the same prompt without pausing.
4. After phase 8: use an Anthropic/Codex model with effort set; expand/collapse via ctrl+t.
5. After phase 11: bare `flow` → TUI up, `ps` shows one child daemon; quit → daemon gone;
   quit mid-run → log ends with a clean `run_ended(aborted)`; `kill -9` the TUI → daemon
   exits within ~2 s; `flow -c` in the same cwd → previous conversation restored.
6. After phase 12: `EDITOR=vim`, ctrl+x ctrl+e round-trips the draft.

## Top risks

- textual × Python 3.14 compatibility — verify first commit of phase 6.
- SSE reconnect races — owned entirely by `EventStream` seq-cursor dedup (phase 3), with a
  dedicated reconnect test; `?follow=true` keepalives must not confuse the parser.
- Anthropic thinking budget vs `max_tokens` interplay (phase 2).
- litellm-derived catalog quality — filter heuristics (`mode == "chat"`,
  `supports_function_calling`) may still admit noise or drop a wanted model; free text is
  the escape hatch.
- Orphaned private daemons — stdin-pipe watchdog (phase 11).
- Two writers on one session log — ACCEPTED risk (decision 9), documented, `flock` later.
- `app.suspend()` tty requirement (phase 12).
