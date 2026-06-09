# Python socket.io server

A Python implementation of Frappe's realtime server, wire-compatible with the
Node implementation (`apps/frappe/socketio.js` + `apps/frappe/realtime/`).
Built on [python-socketio](https://python-socketio.readthedocs.io/) and
uvicorn. Browsers keep using the same `socket.io-client` library and the same
events — no frontend changes are required to switch backends.

```
┌───────────┐  socket.io (ws/polling)  ┌──────────────────────┐
│  Browser   │ ───────────────────────▶ │  this server          │
│ (Desk/SPA) │ ◀─────────────────────── │  (uvicorn, port 9001) │
└───────────┘                          └──────────┬───────────┘
                                          ▲        │ HTTP callback (auth/permissions)
              redis_queue pub/sub         │        ▼
┌───────────┐  "events" channel   ┌───────┴──────┐
│ web/worker │ ──────────────────▶ │ redis_queue  │◀── socketio_auth_secret
│ processes  │  emit_via_redis     └──────────────┘
└───────────┘
```

## How it works

### Multitenancy (dynamic namespaces)

Clients connect to `io(origin + "/" + sitename)` — one socket.io *namespace*
per site. The Node implementation uses `io.of(/^\/.*$/)`; python-socketio has
no regex-namespace equivalent, so `DynamicServer` (server.py) registers all
Frappe event handlers for a namespace the first time any client connects to
it. Invalid sites are rejected by authentication, which requires the
namespace to match the site derived from the request headers.

### Authentication (auth.py)

A direct port of `realtime/middlewares/authenticate.js`:

1. The namespace must match the site resolved from `X-Frappe-Site-Name` /
   `Host` / `Origin` headers (`default_site` for localhost in dev).
2. `Host` and `Origin` hostnames must match.
3. The client must present a `sid` cookie or an `Authorization` header
   (token or Bearer — anything `frappe.api` accepts).
4. The credentials are verified by an HTTP callback to the Frappe web server:
   `GET /api/method/frappe.realtime.get_user_info`, forwarding the client's
   credentials plus the shared `socketio_auth_secret` that web workers store
   in redis_queue. The first call after a cold start can race the secret's
   generation, so it is retried once (same as Node).

The resolved identity (`user`, `user_type`, `installed_apps`) is stored in
the socket session. System Users join the `all` room; everyone joins
`website` and their own `user:{name}` room.

### Event handlers (handlers.py)

Port of `realtime/handlers.js`: `ping`, `doctype_subscribe/unsubscribe`,
`task_subscribe/unsubscribe`, `progress_subscribe`,
`doc_subscribe/unsubscribe`, `doc_open/doc_close` (with `doc_viewers`
presence notifications), `open_in_editor`. `doctype_subscribe`,
`doc_subscribe` and `doc_open` check permissions through an HTTP callback to
`frappe.realtime.has_permission` using the connection's stored credentials.

### Event fan-out (server.py)

`frappe.realtime.publish_realtime` → `emit_via_redis` publishes
`{event, message, room, namespace}` JSON on the redis_queue `events` channel
— unchanged. `consume_events()` subscribes to that channel and emits into
the right room/namespace. Publishes without a room (e.g. the esbuild
`build` event in dev) are broadcast to every connected namespace. The
subscriber reconnects with backoff if redis drops.

An `AsyncRedisManager` is configured as the client manager, so multiple
server processes can be run behind a load balancer and emits reach clients
connected to any instance (the Node implementation is single-process).

### Per-app handlers

The Node server loads `apps/{app}/realtime/handlers.js` from the filesystem.
The Python equivalent is import-based: an app opts in by shipping a
`{app}/realtime_handlers.py` module with a `register(sio, namespace)`
callable, invoked once per site namespace (not per socket — keep
per-connection state in the socket session via `sio.get_session`/
`save_session`). Apps with JS handlers need this (small) port to work with
the Python backend.

## Running it

```sh
# deps are part of frappe's pyproject (python-socketio, uvicorn)
python -m frappe.socketio_server
```

Listens on `socketio_uds` (if set) or `socketio_python_port` (default 9001)
from `common_site_config.json`. Environment overrides: `FRAPPE_BENCH_ROOT`,
`FRAPPE_SITE`, `FRAPPE_REDIS_QUEUE`, `FRAPPE_SOCKETIO_PORT`,
`FRAPPE_SOCKETIO_UDS`.

### Switching backends in development

Both servers can run side by side (Node on 9000, Python on 9001). In a dev
bench (`developer_mode` + dev server), a small indicator appears in the
bottom-right corner showing the active backend — click it to toggle and
reload. Programmatically:

```js
frappe.realtime.get_backend(); // "node" | "python"
frappe.realtime.set_backend("python"); // persists in localStorage, reloads
```

The selection only affects the dev-server connection URL
(`socketio_client.js`); production setups route through nginx and are
controlled by the proxy upstream instead.

### Tests

- `frappe/tests/test_socketio_server.py` — unit tests for config/auth plus
  end-to-end integration tests that boot the real ASGI server and exercise
  auth, permissions and redis fan-out with the python socket.io client
  (`bench --site {site} run-tests --module frappe.tests.test_socketio_server`).
- `cypress/integration/realtime_backend.js` — client-side backend switcher.

## What's needed to run this in production

The server itself is production-shaped (multi-instance capable via the redis
client manager, reconnecting subscriber, UDS support). The pieces below live
outside this repo.

### bench

- **Procfile** (`bench setup procfile`): either replace the Node entry or add
  the Python one alongside:

  ```yaml
  # replace
  socketio: {bench}/env/bin/python -m frappe.socketio_server
  # or run side by side (Node stays on socketio_port 9000)
  socketio_python: {bench}/env/bin/python -m frappe.socketio_server
  ```

- **Supervisor** (`bench setup supervisor`): a `frappe-bench-python-socketio`
  program mirroring the existing node-socketio program, using
  `env/bin/python -m frappe.socketio_server`.

- **nginx** (`bench setup nginx`): the generated config proxies
  `/socket.io/` to `socketio_port`. To cut over, point that upstream at
  `socketio_python_port` (or the UDS path) instead — the HTTP path and
  protocol are identical, so nothing else changes. For a gradual rollout,
  nginx `split_clients` can route a percentage of traffic per backend.

- `bench update`/`bench restart` already restart supervisor programs, so no
  further integration is needed once the program definition exists.

### Frappe Cloud / press

- **Bench image**: no extra system packages — the server is pure Python and
  the dependencies install with frappe. Benches on older frappe versions
  simply don't have the module; press should gate the feature on the app
  version.
- **Supervisor/agent**: press generates supervisor and nginx configs through
  the agent; it needs the same program + upstream changes as plain bench
  (above). Port allocation: either reuse the bench's existing socketio port
  after cutover, or allocate `socketio_python_port` per bench for
  side-by-side operation.
- **Health checks**: the agent's socketio health check can hit
  `GET /socket.io/?EIO=4&transport=polling` — identical for both backends. A
  plain connect to the default namespace also succeeds without auth and is
  used only for health checking.
- **Scaling**: unlike Node, multiple instances can be run behind the same
  nginx upstream (sticky sessions required for long-polling — use
  `ip_hash` or cookie-based stickiness; pure-websocket clients don't need
  it). Emits propagate across instances via the redis client manager.

### Rollout strategy

1. Ship the server in frappe (this directory) — inert until something runs it.
2. bench/press add the supervisor program behind a config flag
   (e.g. `use_python_socketio`), running side by side on 9001.
3. Cut the nginx upstream over per-bench; the Node process keeps serving
   existing connections until drained, clients reconnect to the new backend
   on their next (re)connect.
4. Once stable, drop the Node program and `socketio.js`.

## Known gaps / non-goals

- Apps that ship `realtime/handlers.js` must port them to the Python
  convention (`{app}/realtime_handlers.py`) to keep their custom events when
  a bench switches backends.
- Dynamically-registered namespaces are never garbage-collected (Node sets
  `cleanupEmptyChildNamespaces`). One namespace per site is negligible;
  revisit for very large multitenant benches.
- Auth/permission callbacks run `requests` in a thread per call (mirroring
  Node's per-connect fetch). If connect storms become a bottleneck, switch to
  a shared aiohttp session.
