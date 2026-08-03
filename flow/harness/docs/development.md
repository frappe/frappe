# Development

## Setup

```bash
uv sync --extra dev
uvx pre-commit install
```

Python ≥ 3.14.

## Tests

```bash
uv run pytest
```

- Tests are async (`asyncio_mode = "auto"` in pyproject); write `async def test_...`
  with no marker needed.
- The keyless **`mock`** model drives loop/server tests with no provider. Script exact
  turns with `MockModel(replies=[AssistantMessage(...), ...])` (one consumed per model
  call) and inject it via `Agent(model=mock)`, `session.run(model=mock)`, or by
  monkeypatching `flow.agent.loop.get_model` for HTTP-level tests.
- Live SSE cannot be tested through `httpx.ASGITransport` or the Starlette
  `TestClient` — both buffer whole response bodies. The live-stream test runs a real
  uvicorn server on an ephemeral port; completed-stream tests can use `TestClient`.

Formatting, lint, and types are enforced by pre-commit (ruff + ty). Do not
hand-maintain style — run the hooks.

## Conventions

- **Conventional commits**, atomic and semantic: `feat(scope): …`, `fix(...)`,
  `test(...)`, `docs: …`, `chore: …`. One coherent change per commit.
- Keep comments/docstrings short and precise. No speculative abstractions or config.
- Fixes land in the layer that owns the behavior — see the dependency direction and
  guardrails in [architecture.md](architecture.md) and [rebuild.md](rebuild.md).

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `FLOW_HOST` | `127.0.0.1` | daemon bind host |
| `FLOW_PORT` | `8787` | daemon bind port |
| `FLOW_AUTH_TOKEN` | none | API bearer; required for non-loopback binds |
| `FLOW_DATA_DIR` | `~/.flow/server` | session logs + metadata |
| `FLOW_MODEL` | `mock` | default model name |
| `FLOW_REDIS_URL` | none | if set, every event is also published to `harness:<sid>` |
| `FLOW_ALLOWED_ROOTS` | empty | `os.pathsep`-separated roots for session cwd and path-taking builtins; does not sandbox `bash` (empty = unrestricted) |
| `FLOW_CREDENTIALS_PATH` | `~/.flow/server/credentials.json` | API-key/OAuth store (0600) |

Cross-repo wire identifiers are intentionally kept as `harness:*` (Redis channel,
`X-Harness-Token` header) — they're a contract shared with Flow's bridge.

## Roadmap

**Part 1 — the daemon (done, rebuilt):** durable event substrate → model core → auth +
providers → tools → loop + session → HTTP API + `flow`. The rebuild's contract and
parity audit live in [rebuild.md](rebuild.md).

**Part 2 — client UIs:** a TUI that dogfoods the HTTP/SSE API; a shared
transport-agnostic conversation core; a standalone Vue web shell. End of Part 2 = a
usable standalone coding-agent product.

Part 2 makes the daemon an implementation detail of the client. The CLI surface:

| Command | Behavior |
|---|---|
| `flow` | Start a private daemon on an ephemeral port, open the TUI, and attach to it. Each invocation gets its own daemon; it never adopts one started by `flow serve`. The daemon dies when the TUI exits; quit during an active run aborts and drains without a prompt. `flow -c` continues the most recent session for the current directory instead of creating one. |
| `flow serve` | Start the daemon in the background on the configured host and port, print its address, and return. `--foreground` keeps it attached for supervisors and containers. |
| `flow attach` | Open the TUI against a daemon that is already running — the configured host and port by default, `--url` for any other, `--session` to reopen an existing session. It starts nothing. |
| `flow login` / `logout` / `providers` | Unchanged apart from the program name. |

Daemon lifecycle notes:

- The private daemon is a subprocess of the TUI (`flow serve --foreground --port-file
  --parent-watch`), authenticated with a fresh `FLOW_AUTH_TOKEN` even on loopback. Its
  stdout and stderr go to a log file under `FLOW_DATA_DIR/logs/`. If the TUI dies —
  even by SIGKILL — the daemon's stdin pipe hits EOF and it exits, so orphans cannot
  accumulate. POSIX-only for now.
- A daemon crash is fatal to the TUI: it exits with the log path. There is no
  auto-respawn; sessions are durable, so rerun `flow -c`.
- Discovery of private ephemeral daemons by `flow attach` is out of scope by design.
- **Accepted risk:** two daemons can open the same session file (for example `flow -c`
  in two terminals). Two writers on one append-only log can corrupt it. This is
  documented, not prevented; a future mitigation is a per-session `fcntl.flock`.

The daemon stays the durable side in the `flow serve` + `flow attach` mode: closing
the TUI detaches the client, it does not end the run.

**Part 3 — Flow integration:** Flow adopts the daemon as a client (Frappe proxy
endpoints + a Redis→realtime bridge + the shared core via a Frappe adapter), with Flow's
behavior unchanged.

App-layer features (project instructions, compaction, skills, slash-commands) are
deferred to post-v1.
