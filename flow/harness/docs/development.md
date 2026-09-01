# Development

## Setup and checks

Flow requires Python 3.14 or newer.

```bash
uv sync --extra dev
uvx pre-commit install
uv run pytest
uv run ruff check .
uv run ty check
```

Tests use `pytest-asyncio` automatic mode. Use the keyless `mock` model for loop and server tests. For a live SSE test, start a real Uvicorn server on an ephemeral port; in-process ASGI transports buffer streaming responses.

Formatting and static checks use Ruff and ty. The codebase uses tabs, double quotes, and a 110-character Ruff line limit.

## Run Flow

| Command | Behavior |
| --- | --- |
| `flow` or `flow tui` | Starts a private Unix-socket daemon and opens the Textual UI. |
| `flow -c` | Opens the most recent session for the current directory. |
| `flow serve` | Runs the daemon on the configured host and port. |
| `flow serve --background` | Starts a detached daemon and prints its address. |
| `flow web` | Serves the built Vue UI and opens a browser. Use `--no-browser` to suppress it. |
| `flow attach` | Opens the TUI against an existing daemon. `--session` selects a session. |
| `flow login`, `flow logout`, `flow providers` | Manage provider credentials. |

The private daemon used by `flow` has a fresh bearer token, a private socket, and exits when its parent TUI exits. It is POSIX-only. `flow serve` is the long-lived option; closing an attached client never stops its run.

Build the web UI before `flow web` if packaged assets are unavailable:

```bash
cd ui
npm install
npm run build -w app
```

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `FLOW_HOST` | `127.0.0.1` | TCP bind host for `flow serve`. |
| `FLOW_PORT` | `8787` | TCP port. |
| `FLOW_DATA_DIR` | `~/.flow/server` | Session data and daemon logs. |
| `FLOW_AUTH_TOKEN` | unset | Bearer token for the daemon API; required for non-loopback TCP binds. |
| `FLOW_AUTH_TOKEN_FILE` | unset | File holding the bearer token, so an operator can generate and rotate it; used when `FLOW_AUTH_TOKEN` is unset. A configured but missing or empty file is a startup error. |
| `FLOW_TENANTS_FILE` | unset | Multi-tenant mode for `flow serve`: a JSON file mapping each site to its bearer token and optional `allowed_roots` — `{"site1.localhost": {"token": "…", "allowed_roots": ["…"]}}`. A request's token names its site; each site's sessions live under `data_dir/tenants/<site>` and are invisible to other sites. Mutually exclusive with the single-token variables. |
| `FLOW_PROFILE` | `local` | Policy preset for `flow serve` (`--profile` overrides). `local` keeps everything on; `deployed` caps tools to `read_file` and `grep`, refuses to start without an auth token (even on a unix socket), and answers 403 on everything outside the core session verbs: `/fs/*`, the session file diff, `/models`, `/providers*`, and the extension and skill routes. |
| `FLOW_CALLBACK_HOSTS` | unset | Comma-separated `host[:port]` values a session `callback_url` may target. Enforced by the `deployed` profile; unset there means client callbacks are refused. |
| `FLOW_POLICY` | unset | JSON object overriding individual policy fields of the chosen profile for `flow serve`, e.g. `{"skills_api": true, "tool_allowlist": ["read_file", "grep", "bash"]}`. Applied last, so it wins over the profile and `FLOW_CALLBACK_HOSTS`; unknown fields or wrong types refuse startup. |
| `FLOW_CREDENTIALS_PATH` | `~/.flow/server/credentials.json` | Credential-store path. |
| `FLOW_MODEL` | `mock` | Initial model for a new TUI session; a saved TUI choice is used when it is unset. |
| `FLOW_ALLOWED_ROOTS` | unset | `os.pathsep`-separated roots for session directories and path-taking tools. It does not sandbox `bash`. |
| `FLOW_CORS_ORIGINS` | unset | Comma-separated browser origins allowed to call the API. |
| `FLOW_REDIS_URL` | unset | Publishes every event to `harness:<session-id>`. |

Use `-e PATH` to load a Python extension and `--no-extensions` to omit the global extension directory. See [tools.md](tools.md).

## Change boundaries

Keep behavior in the layer that owns it: provider protocols in adapters, model/tool control flow in the loop, durability and state transitions in `Session`, and HTTP/TUI presentation at their edges. Update tests and the relevant concise documentation with behavior changes.
