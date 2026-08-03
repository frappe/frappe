# Flow TUI — phased implementation plan

## Context

`flow` is a durable agent daemon: FastAPI + SSE server, tree-shaped session log, typed
pydantic event contract (`src/flow/events.py`). Today bare `flow` runs the server in the
foreground and there is no client UI. `docs/development.md` (Part 2) already plans the
target surface: bare `flow` starts a private daemon on an ephemeral port and attaches a
TUI; `flow serve` runs the daemon in the background; `flow attach` connects to a running
daemon.

This plan builds that TUI on textual (which bundles rich), with a transport-agnostic
client core that a future Vue web shell can reuse. Decisions already made with the user:

1. The bare-`flow` private daemon dies when its TUI exits.
2. Model catalog lives server-side: new `GET /models` endpoint; picker also accepts free text.
3. Reasoning effort gets full server plumbing (SessionConfig → LoopInputs → `get_model(params=...)`).
4. System prompt is composed client-side: base prompt + `~/AGENTS.md` + project `AGENTS.md`
   (walk up from cwd) + `~/.agents/` skills index, sent via `SessionConfig.system_prompt`.

Ground truths that shape the plan (verified in code):

- `bash` has `requires_confirmation=True` → approvals UI must land right after the TUI shell,
  or the first shell command deadlocks the session.
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
src/flow/
  client/                 # transport-agnostic core (Vue shell reuses this)
    api.py                # FlowClient: async httpx wrapper over the HTTP API
    stream.py             # SSE parser + reconnecting EventStream with since-cursor
    state.py              # ConversationState reducer (pure, no I/O)
    system_prompt.py      # base prompt + AGENTS.md discovery + ~/.agents index
  tui/
    app.py                # FlowApp(App)
    controller.py         # FlowClient + EventStream + ConversationState → widget updates
    commands.py           # command registry (slash + palette share it)
    screens/pickers.py    # ModelPicker, EffortPicker (ModalScreen)
    widgets/
      conversation.py     # VerticalScroll of per-message widgets
      messages.py         # UserMessageView, AssistantMessageView, ThinkingBlock, ToolCallView
      approval.py         # inline approval card
      composer.py         # TextArea input, slash dispatch, editor hook
      status_bar.py
    styles.tcss
  cli/
    daemon.py             # spawn/readiness/teardown for private + background daemons
    main.py               # reshaped: flow / serve / attach / login / logout / providers
```

Each phase is one PR-sized commit with tests. Phases 1–2 are server-only; 3–5 are the shared
core; 6–10 build the TUI against a manually run `flow serve`; 11 lands daemon lifecycle;
12 is isolated polish.

---

## Phase 1 — Server: `GET /models` and `GET /sessions`

**Files:** `src/flow/model/catalog.py`, `src/flow/server/app.py`, `src/flow/session/store.py`, tests.

- Extend `ProviderSpec` with `models: tuple[str, ...]` — short curated list per provider
  (full names, e.g. `anthropic/claude-sonnet-4-5`, `codex/gpt-5.1-codex`). Static, no network.
- Factor the credential-availability predicate out of `login.show_providers`
  (`src/flow/cli/login.py:62`) so login and the endpoint share it.
- `GET /models` → `{"models": [{"name", "provider", "available": bool}]}`. Return all with a
  flag (picker greys out unavailable) instead of filtering.
- `SessionStore.list()` reads `*.meta.json` cheaply (no log replay); `GET /sessions` →
  `[{session_id, state, model, latest_seq, cwd}]`.

**Test:** TestClient; models with/without credentials (tmp CredentialStore + env monkeypatch);
session list including a cold on-disk session (new store over the same dir).

## Phase 2 — Server: reasoning-effort plumbing

**Files:** `src/flow/session/config.py`, `src/flow/events.py` (`ModelChanged`),
`src/flow/session/session.py`, `src/flow/server/app.py`, `src/flow/agent/loop.py`,
new `src/flow/model/reasoning.py`.

- `SessionConfig.reasoning_effort: Literal["low","medium","high"] | None = None`.
- `ModelChanged.reasoning_effort` (durable, per-branch, survives rewind); `set_model` and
  `SetModelRequest` accept it; expose current value in `GET /sessions/{sid}`.
- `LoopInputs.reasoning_effort`; `_authenticated_model` passes
  `params=reasoning_params(inputs.model_name, effort)`.
- `reasoning.py: reasoning_params(model, effort) -> dict | None`:
  - `anthropic/*` → `{"thinking": {"type": "enabled", "budget_tokens": {low: 4096, medium: 12288, high: 32768}[effort]}}`
  - litellm path (openai, gemini, xai, …) → `{"reasoning_effort": effort}` (litellm unified param)
  - `codex/*` → map onto Codex `reasoning.effort`; verify `providers/codex.py` reads it from
    `params`, add pass-through if absent.
- Old `ModelChanged` rows replay fine (pydantic default None).

**Risk:** Anthropic `thinking` needs `max_tokens` headroom — verify against `LiteLLMModel`
request assembly; `budget_tokens` must be below max output tokens.

**Test:** unit-test `reasoning_params`; loop test with monkeypatched `get_model` capturing
`params`; server test: create with effort → change via `/model` → rewind restores prior effort.

## Phase 3 — Client core: `FlowClient` + reconnecting `EventStream`

**Files:** new `src/flow/client/{api,stream}.py`, `tests/test_client.py`.

- Async httpx (Textual is asyncio; sync would force threads). `FlowClient(base_url, token=None)`
  with typed methods for every endpoint. Reuse `flow.events.parse_event` and `SessionConfig`
  directly — no parallel shapes.
- `EventStream(client, sid, since=0)` async iterator: open `/stream?since=cursor`, yield parsed
  events, advance cursor only on durable events with seq, drop `seq <= cursor` (reconnect races
  never double-render). Server closes at end of run → reconnect after short delay (0.2 s idle,
  backoff on transport error). `stop()` closes cleanly. Wake-signal channel is a noted future
  refinement.

**Test:** REST via `httpx.ASGITransport`; stream reconnect via real uvicorn on port 0
(existing pattern in `tests/test_server.py`): two runs with MockModel, assert each durable
event yielded exactly once across the server-side close between runs.

## Phase 4 — Client core: `ConversationState` reducer

**Files:** new `src/flow/client/state.py`, `tests/test_client_state.py`.

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

## Phase 5 — Client core: system-prompt builder

**Files:** new `src/flow/client/system_prompt.py`, `tests/test_system_prompt.py`.

- `build_system_prompt(cwd, home=None) -> str`:
  1. Base coding-agent prompt (module constant; replaces the daemon default client-side).
  2. `~/AGENTS.md` if present (global instructions section).
  3. Project `AGENTS.md`: walk up from cwd to home (or root), outermost-first so nearer files
     override by recency.
  4. `~/.agents/*.md` as a skills index (name + first heading), not full contents — bounded
     token cost, minimal layout assumption.
- Sections joined with provenance headers (`# Project instructions (/path/AGENTS.md)`).

**Test:** tmp_path trees with nested AGENTS.md, missing files; `home` is a parameter so no
`Path.home` monkeypatching.

## Phase 6 — TUI shell MVP (`flow attach --url` only)

**Files:** new `src/flow/tui/{app,controller}.py`,
`widgets/{conversation,messages,composer,status_bar}.py`, `styles.tcss`; `pyproject.toml`
(add `textual` to deps, `textual-dev` to dev); `cli/main.py` (add `attach` with required
`--url`, new session by default via `build_system_prompt(cwd)` + `POST /sessions` with
`cwd=os.getcwd()`); `tests/test_tui_shell.py`.

- **Per-message widgets in `VerticalScroll`, not `RichLog`** — needed for delta updates
  in place, delta→durable replacement, collapsible thinking (phase 8), and interactive
  approval cards (phase 7). One widget per durable entry + one mutable `PartialAssistantView`
  at the tail, swapped when the durable message arrives. Anchor scroll to bottom unless the
  user scrolled up.
- Controller owns `FlowClient`, `EventStream` (Textual worker), `ConversationState`; widgets
  never touch httpx → pilot-testable with a fake controller.
- Composer: `TextArea`; Enter submits, `ctrl+j` inserts newline. Submit while running =
  steering (server answers `{"status":"steered"}`; show a marker). One `ctrl+c`/Escape aborts
  the run; second prompts quit.
- Status bar: model · effort · state · Σ tokens · cost · session id.
- Renders: user/assistant text, tool call one-liner + result preview, run_error banner,
  retry status ("retrying 2/5 in 3 s"). Thinking as plain dimmed text for now.
- **Interim stopgap:** create sessions with `auto_approve=True` for this phase only (bash
  gates by default and approvals UI is phase 7). Phase 7 removes it.

**Risk:** textual on Python 3.14 — verify import + `run_test()` as the first commit of this
phase; fall back to a newer textual pre-release if broken. Long-transcript reflow cost is
accepted for MVP (`entries?path=active` seeding + virtualization later).

**Test:** `App.run_test()` pilot with a fake controller: rendering, delta→durable swap,
steering, status bar. One integration pilot against real uvicorn + MockModel.

## Phase 7 — Approvals UI + pause/resume

**Files:** new `src/flow/tui/widgets/approval.py`; `controller.py`, `messages.py`; tests.

- On `pending_approval`: `ApprovalCard` per pending call at the log tail — prompt text,
  `[a]pprove [d]eny`, free-text input (free text = redirect per contract), "approve all"
  shortcut for batches. Submit → `POST resume {approval_seq, answers}`; card collapses into
  a verdict line. Bind `cancel_pending` for abandoning a paused run.
- Status bar shows `paused — awaiting approval`; composer disabled with a hint while paused.
- Remove the phase-6 `auto_approve` stopgap.

**Test:** pilot drives `approval_required` → key presses → assert resume payload; integration
with MockModel scripting a bash call → approve → run completes.

## Phase 8 — Thinking traces (collapsible) + tool-result rendering

**Files:** `src/flow/tui/widgets/messages.py` (add `ThinkingBlock` on textual `Collapsible`),
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

**Files:** new `src/flow/tui/commands.py`; `composer.py`, `app.py`; tests.

- `Command(name, description, run, arg_hint)` in a module registry with a `@command`
  decorator. Initial set: `/model`, `/effort`, `/abort`, `/rewind [seq]` (default: last user
  message), `/new`, `/sessions` (switch via `GET /sessions`), `/help`, `/quit`.
- Composer intercepts leading `/`; unknown command → inline error. Autocomplete deferred.
- Use textual's built-in `CommandPalette` with a custom `Provider` fuzzy-matching the same
  registry; bind explicitly to `ctrl+p`.

**Test:** registry parse/dispatch unit tests; pilot: `/abort` reaches controller; palette
opens and runs a command.

## Phase 10 — Model + effort pickers

**Files:** new `src/flow/tui/screens/pickers.py`; wire into `commands.py`; tests.

- `ModelPicker(ModalScreen)`: `Input` filter over `OptionList` fed by `GET /models`;
  available first, unavailable greyed with a `flow login <provider>` hint; Enter with no
  highlighted option submits the raw filter text (free-text path). Result → `set_model`.
- `EffortPicker`: default/low/medium/high → `set_model(..., reasoning_effort=x)`.
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
- Teardown: TUI `finally:` → `terminate()`, 3 s grace, `kill()`. Orphan safety even under
  SIGKILL of the TUI: `--parent-watch` spawns a thread in the child that blocks reading
  inherited stdin; EOF (parent died) → `os._exit(0)`.
- Crash handling: stream loop hits connection-refused and `proc.poll() is not None` → fatal
  modal with daemon log path; no auto-respawn (sessions are durable; rerun `flow`).
- CLI surface:
  - `flow` → spawn private daemon (data dir stays `FLOW_DATA_DIR` — daemon is ephemeral,
    session logs persist), create session, run TUI, teardown.
  - `flow serve` → background via `start_new_session=True`, print address, exit;
    `--foreground` keeps current behavior. POSIX-only for now (note in docs).
  - `flow attach [--url] [--session]` → default `http://{FLOW_HOST}:{FLOW_PORT}`, token from
    `FLOW_AUTH_TOKEN`; session picker over `GET /sessions`; starts nothing. Discovery of
    private ephemeral daemons stays out of scope by design.

**Test:** lifecycle without the TUI: spawn helper → healthz OK with token / 401 without;
terminate → gone; orphan test: close parent pipe end, child exits ≤2 s. Extend
`tests/test_cli.py` for parsing.

## Phase 12 — External editor (`ctrl+x ctrl+e`) + composer polish

**Files:** `src/flow/tui/widgets/composer.py`, `app.py`; tests.

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
3. After phase 7: run a prompt that triggers `bash`; approve, deny, and redirect paths.
4. After phase 8: use an Anthropic/Codex model with effort set; expand/collapse via ctrl+t.
5. After phase 11: bare `flow` → TUI up, `ps` shows one child daemon; quit → daemon gone;
   `kill -9` the TUI → daemon exits within ~2 s; rerun `flow` → previous session log intact
   on disk.
6. After phase 12: `EDITOR=vim`, ctrl+x ctrl+e round-trips the draft.

## Top risks

- textual × Python 3.14 compatibility — verify first commit of phase 6.
- SSE reconnect races — owned entirely by `EventStream` seq-cursor dedup (phase 3), with a
  dedicated two-run reconnect test.
- Anthropic thinking budget vs `max_tokens` interplay (phase 2).
- Orphaned private daemons — stdin-pipe watchdog (phase 11).
- `app.suspend()` tty requirement (phase 12).
