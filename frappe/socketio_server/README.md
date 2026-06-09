# socketio_server (prototype)

Drop-in replacement sketch for `apps/frappe/socketio.js`, in Python via
`python-socketio` + `uvicorn`. Not wired into bench yet.

## To try it

1. Install deps in the frappe venv:
   ```
   uv pip install "python-socketio[asyncio]" uvicorn redis
   ```

2. Stop the existing node socketio (`mprocs` → kill `socketio`), then:
   ```
   uvicorn frappe.socketio_server.server:asgi_app --host 0.0.0.0 --port 9000
   ```

3. Replace the Procfile line:
   ```
   # before
   socketio: node apps/frappe/socketio.js
   # after
   socketio: .venv/bin/uvicorn frappe.socketio_server.server:asgi_app --host 0.0.0.0 --port 9000
   ```

## Wire compatibility

- `socket.io-client` (browser) connects unchanged: `io(origin + "/" + site)`.
- Redis `events` channel contract unchanged — `frappe.realtime.emit_via_redis`
  publishes the same JSON shape; `consume_events()` in `server.py` fans it out.
- Per-app handler discovery moves from `apps/{app}/realtime/handlers.js` (filesystem)
  to `hooks.py` (`realtime_handlers = "myapp.realtime.setup"`). Apps that depend
  on the JS version need to declare the hook.

## Known gaps / TODOs

- `DynamicServer._handle_connect` is the namespace workaround. If python-socketio
  ever adds regex namespaces, drop the subclass.
- `auth.py` reuses `frappe.init/connect/destroy` per connect — fine for low
  concurrency, needs a session-pool wrapper for production.
- `_check_permission` is sync inside an async handler — wrap in
  `asyncio.to_thread()` once we benchmark.
- No tests yet. First test should round-trip an `emit_via_redis` → browser.
