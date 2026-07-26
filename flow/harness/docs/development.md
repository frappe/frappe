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
  call) and inject it via `Agent(model=mock)` or the loop's `model=` param.

Formatting, lint, and types are enforced by pre-commit (ruff + pyright). Don't
hand-maintain style - run the hooks.

## Conventions

- **Conventional commits**, atomic and semantic: `feat(scope): …`, `fix(...)`,
  `test(...)`, `docs: …`, `chore: …`. One coherent change per commit.
- Keep comments/docstrings short and precise. No speculative abstractions or config.

## Configuration (env vars)

| Var | Default | Purpose |
|---|---|---|
| `FLOW_SERVER_HOST` | `127.0.0.1` | daemon bind host |
| `FLOW_SERVER_PORT` | `8787` | daemon bind port |
| `FLOW_SERVER_AUTH_TOKEN` | none | API bearer; required for non-loopback binds |
| `FLOW_SERVER_DATA_DIR` | `~/.flow/server` | session logs + metadata |
| `FLOW_SERVER_MODEL` | `mock` | default model name |
| `FLOW_SERVER_REDIS_URL` | none | if set, every event is also published to `harness:<sid>` |
| `FLOW_SERVER_ALLOWED_ROOTS` | empty | `os.pathsep`-separated cwd fence (empty = unrestricted) |
| `FLOW_SERVER_CREDENTIALS_PATH` | `~/.flow/server/credentials.json` | API-key/OAuth store (0600) |

Cross-repo wire identifiers are intentionally kept as `harness:*` (Redis channel,
`X-Harness-Token` header) - they're a contract shared with Flow's bridge.

## Roadmap

**Part 1 - the daemon (done):** durable event substrate → model layer → auth foundation
→ tools → agent loop → uniform HTTP API + `flowd`.

**Part 2 - client UIs:** a TUI (`flowd chat`, dogfooding the HTTP/SSE API); a shared
transport-agnostic conversation core; a standalone Vue web shell. End of Part 2 = a
usable standalone coding-agent product.

**Part 3 - Flow integration:** Flow adopts the daemon as a client (Frappe proxy
endpoints + a Redis→realtime bridge + the shared core via a Frappe adapter), with Flow's
behavior unchanged.

App-layer features (project instructions, compaction, skills, slash-commands) are
deferred to post-v1.
