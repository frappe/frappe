# Development

## Setup and checks

Flow requires Python 3.14 or newer.

The PyPI distribution is `frappe-flow`, the Python import package is `flow_harness`,
and the command is `flow`. The separate import name lets the harness coexist with
the Frappe app's `flow` package in one environment. Extensions and Python clients
using the former `flow` imports must update them to `flow_harness` and reinstall
the harness. There is no `flow` compatibility package, because it would collide
with the Frappe app again.

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
| `flow` or `flow web` | Serves the built Vue UI and opens a browser. Use `--no-browser` to suppress it. |
| `flow tui` | Starts a private Unix-socket daemon and opens the Textual UI. |
| `flow tui -c` | Opens the most recent session for the current directory. |
| `flow serve` | Runs the daemon on the configured host and port, logging one timestamped line per request. |
| `flow serve --background` | Starts a detached daemon and prints its address. |
| `flow attach` | Opens the TUI against an existing daemon. `--session` selects a session. |
| `flow login`, `flow logout`, `flow providers` | Manage provider credentials. |

The private daemon used by `flow tui` has a fresh bearer token, a private socket, and exits when its parent TUI exits. It is POSIX-only. `flow serve` is the long-lived option; closing an attached client never stops its run.

Build the web UI before `flow` or `flow web` if packaged assets are unavailable:

```bash
cd ui
npm ci
npm run build -w app
```

Packaging does this for you: a source-tree `uv build` always runs the same npm build,
so both the wheel and source distribution carry the current UI. A wheel built from an
sdist reuses the compiled UI already inside it. Only an editable source checkout needs
the manual step above.

## Environment

| Variable | Default | Meaning |
| --- | --- | --- |
| `FLOW_HOST` | `127.0.0.1` | TCP bind host for `flow serve`. |
| `FLOW_PORT` | `8787` | TCP port. |
| `FLOW_DATA_DIR` | `~/.flow/server` | Session data and daemon logs. |
| `FLOW_AUTH_TOKEN` | unset | Bearer token for the daemon API; required for non-loopback TCP binds. |
| `FLOW_AUTH_TOKEN_FILE` | unset | File holding the bearer token, so an operator can generate and rotate it; used when `FLOW_AUTH_TOKEN` is unset. A configured but missing or empty file is a startup error. |
| `FLOW_TENANTS` | unset | Multi-tenant mode for `flow serve`: a JSON template every site's tenant is filled in from, `{site}` standing for the site's name — `{"token_file": "/bench/sites/{site}/site_config.json", "token_key": "flow_server_secret", "allowed_roots": ["/bench/sites/{site}/public/files"], "data_dir": "/bench/sites/{site}/private/flow"}`. A request names its site in `X-Flow-Site` and sends that site's token as its bearer; the daemon reads the token from the site's `token_file` (key `token_key`), so a site works as soon as its file holds a token and is refused once it does not. `allowed_roots` is required: each site is fenced to its own paths. Optional: `ignore_hidden_files`; `callback_hosts`, which replaces `FLOW_CALLBACK_HOSTS`; `callback_headers`, sent on every callback; `data_dir`, which must contain `{site}` (default `data_dir/tenants/<site>`); `extensions`. Disables the provider and credential routes: the credential store is daemon-wide, so no site token may manage it. Mutually exclusive with the single-token variables. |
| `FLOW_PROFILE` | `local` | Policy preset for `flow serve` (`--profile` overrides). `local` keeps everything on; `deployed` hardens a daemon that fronts a remote client — what it caps, refuses and logs is listed in [api.md](api.md#http-basics). |
| `FLOW_CALLBACK_HOSTS` | unset | Comma-separated `host[:port]` values a session `callback_url` may target. Enforced by the `deployed` profile; unset there means client callbacks are refused. The `callback_hosts` of `FLOW_TENANTS` replaces it for every site. |
| `FLOW_POLICY` | unset | JSON object overriding individual policy fields of the chosen profile for `flow serve`, e.g. `{"skills_api": true, "tool_allowlist": ["read", "grep", "bash"]}`. Applied last, so it wins over the profile and `FLOW_CALLBACK_HOSTS`; unknown fields or wrong types refuse startup, as does switching off `require_auth` or `audit_log` where the profile guarantees them. |
| `FLOW_CREDENTIALS_PATH` | `~/.flow/server/credentials.json` | Credential-store path. |
| `FLOW_CODEX_CLIENT_VERSION` | unset | Codex version sent when listing the Codex catalog, which hides models newer than it. Unset, Flow sends `999.0.0` so none are hidden; set a real Codex version if the catalog ever rejects that. |
| `FLOW_MODEL` | `mock` | Initial model for a new TUI session; a saved TUI choice is used when it is unset. |
| `FLOW_ALLOWED_ROOTS` | unset | `os.pathsep`-separated roots for session directories and path-taking tools. It does not sandbox `bash`. |
| `FLOW_CORS_ORIGINS` | unset | Comma-separated browser origins allowed to call the API. |
| `FLOW_SESSION_CACHE_MB` | `64` | Memory the daemon may spend holding live sessions in memory, across every site it serves. Past it, the least recently used are dropped and rebuilt from their logs on the next call; a session with a live run, a live stream, or a title being written is never dropped. |
| `FLOW_REDIS_URL` | unset | Publishes events without blocking runs. Site events use `harness:<site>:<session-id>`; other events use `harness:<session-id>`. Messages keep their event fields at the top level and add `session_id`, `stream_id`, `revision`, and, for tenants, `site`. |
| `FLOW_REDIS_MAX_PENDING_PER_SITE` | `128` | Maximum queued events across a site's sessions. |
| `FLOW_REDIS_MAX_PENDING` | `1024` | Maximum queued events across the daemon. |

Use `-e PATH` to load a Python extension and `--no-extensions` to omit the global extension directory. See [extensions.md](extensions.md).

Redis uses one async worker and one FIFO queue per site. Each active site gets one publishing turn. Events stay ordered within each site; sessions within a site share its allowance without separate limits or scheduling. Non-tenant sessions share a separate local queue with the same limit. Empty site queues are removed. The server lifecycle starts and stops the worker. Session commits only enqueue events; they never wait for Redis.

Both limits must be positive integers. They count queued events, not bytes, and exclude the one publish in flight. The first limit reached rejects the new event. A busy session can fill its site's queue; combined load can fill the total allowance. These limits are burst buffers, not rate limits or a Redis outage backlog. They do not protect slow downstream subscribers.

Overflow or a publish failure requests resync on `harness-resync:site:<site>`, or `harness-resync:local` for non-tenant sessions. A notice such as `{"type":"resync_required","session_ids":["one","two"]}` refreshes only those tracked sessions in that scope. Session IDs never cross site scopes, even when two sites use the same ID.

Repeated drops are combined. Each notification batch tracks at most 128 session IDs per scope; exceeding that limit removes `session_ids`, requesting resync for all tracked sessions in that scope. Each batch tracks at most 1024 scopes; exceeding that limit replaces the batch with `{"type":"resync_required"}` on `harness-resync:all`. Relays must subscribe to their scoped resync channels and this global fallback, as well as their session channels. A relay that ignores `session_ids` still recovers safely, but refreshes the entire scope.

Failed notices retry even when no new events arrive. Drops during a publish are kept for the next notice. Queue overflow logs a warning per affected scope and pending batch. Serialization errors are logged separately: the invalid event is dropped and requests resync, but does not mark Redis offline or stop the worker. Shutdown allows two seconds to drain, cancels a stalled worker, then allows half a second for connection cleanup.

The pattern `harness-resync:*` matches all resync notices and no session-event channels. The explicit `site:` segment keeps sites named `all` or `local` distinct from those scopes.

Redis remains best-effort. Relays must catch up after subscribing or reconnecting and periodically check tracked runs, since a disconnected subscriber can miss any notification. See [api.md](api.md#entries-and-streaming) for snapshot ordering. Harness authenticates sites; Frappe must check user permissions before forwarding events or snapshots.

Custom sinks still accept `(session_id, event)`. The event dictionary adds `stream_id` and `revision`, plus `site` in tenant mode. These fields are transport metadata, not stored event fields.

When embedding `RedisEventSink`, pass it as the store's `event_sink` and pass `lifespan=sink.lifespan` to `create_app`. The `max_pending_per_site` and `max_pending` arguments set its limits. Call the sink only on that server's event loop; its queues are not thread-safe. Constructing the sink does not start publishing.

### Redis capacity checks

The defaults favor dropping and resyncing over retaining a long backlog. Larger queues can absorb longer stalls, but also retain more events that a recovering consumer may discard after its snapshot. They are starting budgets, not a production throughput guarantee. Tune them for active sessions, event sizes, and brief publishing stalls. Watch queue-full warnings, resync notices, and publishing failures. Increasing a queue cannot fix sustained overload.

With `redis-server` installed, run the isolated load tests:

```bash
FLOW_RUN_REDIS_LOAD_TESTS=1 uv run pytest tests/test_redis_sink_load.py -q -s
```

They use a temporary Redis with persistence disabled, not the bench Redis. The workload has 8 sites with 16 sessions each, 40 events per session, and 256-byte text chunks. One test produces 20 events per second per session and checks delivery without drops. The other submits all 5120 events at once and checks that only 1024 are buffered, with targeted resync notices for the dropped events. Both verify session ordering and report throughput and p99 latency. Repeat on deployment-like hardware and with representative payload sizes before choosing production limits. This measures Harness-to-Redis delivery, not Frappe-to-browser delivery.

## Change boundaries

Keep behavior in the layer that owns it: provider protocols in adapters, model/tool control flow in the loop, durability and state transitions in `Session`, and HTTP/TUI presentation at their edges. Update tests and the relevant concise documentation with behavior changes.
