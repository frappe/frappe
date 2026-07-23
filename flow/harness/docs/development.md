# Development

## Setup

```bash
pip install -e ".[dev]"          # or: uv pip install -e ".[dev]"
```

Python ≥ 3.11. Runtime deps: fastapi, uvicorn, httpx, pydantic, litellm, redis.

## Tests & lint — the clean bar

```bash
python -m pytest            # the whole suite
ruff check src tests        # must pass — this is the clean bar
```

- Tests are async (`asyncio_mode = "auto"` in pyproject); write `async def test_...`
  with no marker needed.
- The keyless **`mock`** model drives loop/server tests with no provider. Script exact
  turns with `MockModel(replies=[AssistantMessage(...), ...])` (one consumed per model
  call) and inject it via `Agent(model=mock)` or the loop's `model=` param.
- **`ruff check` is the standard, not `ruff format`.** Do not run `ruff format` — it
  reflows content and can't stay space-clean on docstrings.

## Conventions

- **Tabs for indentation** (matching Frappe convention), not spaces. Convert code
  indentation only — never touch whitespace inside docstrings/string literals.
- **Line length 100.** Ruff rule set: `E, F, I, UP, B`.
- **Conventional commits**, atomic and semantic: `feat(scope): …`, `fix(...)`,
  `test(...)`, `docs: …`, `chore: …`. One coherent change per commit.
- Keep comments/docstrings short and precise. No speculative abstractions or config.

## Layout

```
src/flow_server/
  events.py            event protocol
  config.py            env-overridable daemon defaults
  session/             log.py (durable seq-log), store.py (Session/Config/Store)
  model/               model.py (Model + LiteLLMModel), mock.py, __init__.py (get_model)
                       auth.py, credentials.py, providers/  (native OAuth foundation)
  tools/               tool.py (Tool/@tool/schema), builtins/ (bash/read_file/write/edit/grep)
  agent/               loop.py (the loop), agent.py (the Agent facade)
  server/              app.py (FastAPI routes + SSE)
  cli/                 main.py (flowd serve)
tests/                 one test_*.py per concern
docs/                  you are here
```

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `FLOW_SERVER_HOST` | `127.0.0.1` | daemon bind host |
| `FLOW_SERVER_PORT` | `8787` | daemon bind port |
| `FLOW_SERVER_DATA_DIR` | `./.flow-server-data` | session logs + metadata |
| `FLOW_SERVER_MODEL` | `mock` | default model name |
| `FLOW_SERVER_REDIS_URL` | none | if set, every event is also published to `harness:<sid>` |
| `FLOW_SERVER_ALLOWED_ROOTS` | empty | `os.pathsep`-separated cwd fence (empty = unrestricted) |
| `FLOW_SERVER_CREDENTIALS_PATH` | `~/.flow-server/credentials.json` | OAuth token store (0600) |

Cross-repo wire identifiers are intentionally kept as `harness:*` (Redis channel,
`X-Harness-Token` header) — they're a contract shared with Flow's bridge.

## Roadmap

**Part 1 — the daemon (done):** durable event substrate → model layer → auth foundation
→ tools → agent loop → uniform HTTP API + `flowd`.

**Part 2 — client UIs:** a TUI (`flowd chat`, dogfooding the HTTP/SSE API) + `flowd
login` for native-provider OAuth; a shared transport-agnostic conversation core; a
standalone Vue web shell. End of Part 2 = a usable standalone coding-agent product.

**Part 3 — Flow integration:** Flow adopts the daemon as a client (Frappe proxy
endpoints + a Redis→realtime bridge + the shared core via a Frappe adapter), with Flow's
behavior unchanged.

App-layer features (project instructions, compaction, skills, slash-commands) are
deferred to post-v1.
