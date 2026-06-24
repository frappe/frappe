# Realtime handlers for custom apps

This is the Python Socket.IO realtime server (`python -m frappe.realtime.server`).
It runs as a **separate gevent process** from the web/gunicorn process.

This guide is for app authors who want to add their own realtime events. You do not need to touch this folder — you register handlers from inside your own app.

## Where your handlers go

Put your handlers in:

```text
your_app/your_app/realtime/handlers.py
```

The server imports `<app>.realtime.handlers` for every app installed on the site at startup. If the module is missing, your app simply has no realtime handlers — that is fine. If the module exists but raises on import, the server **fails loudly at startup** (it does not swallow the error), so a broken handler file is caught immediately.

## Writing a handler

```python
import frappe
from frappe.realtime import Socket, realtime


@realtime.on("project_subscribe")
def project_subscribe(socket: Socket, project: str) -> None:
    if socket.has_permission("Project", project):
        socket.join(f"project:{project}")
```

- The event name (`"project_subscribe"`) is what the browser emits with `frappe.realtime.on(...)` / the client's `socket.emit(...)`.
- The first argument is always the typed `Socket`. The rest are the payload the client sent, positionally.
- The decorator returns the function unchanged — it is a plain function you can also call/test directly.

### Decorator options

```python
@realtime.on(
    "project_subscribe",
    frappe_context=False,   # open a Frappe context (DB + session) for the handler body
    allow_guest=False,      # if False, the event is dropped when socket.user == "Guest"
)
```

Defaults: `frappe_context=False`, `allow_guest=False`.

## Install scoping (important)

A handler runs only if **its owning app is installed on the connecting site**. The owning app is detected automatically from the import — you do not declare it. So a handler in `your_app/realtime/handlers.py` runs only for sockets on sites that have
`your_app` installed. Nothing leaks across apps or sites.

## The `Socket` object

Read-only identity (populated at connect, from the web process):

```python
socket.site            # str  — the site this socket is on
socket.user            # str  — "Guest" for anonymous
socket.user_type       # str  — e.g. "System User"
socket.installed_apps  # list[str]
```

Rooms and emit:

```python
socket.join(room)                       # add this socket to a room
socket.leave(room)                       # remove it
socket.emit(event, data=None, room=None) # emit to a room, or to this client if room is None
```

Permission check (default, cheap — no DB in the realtime process):

```python
socket.has_permission(doctype, name=None) -> bool   # HTTP call to the web process
```

Transient per-socket state (cleared when the socket disconnects):

```python
socket.set("key", value)
socket.get("key", default=None)
```

## Permission checks: two ways

Pick one per handler; do not mix silently.

1. **HTTP (default, recommended).** `socket.has_permission(doctype, name)` asks the web process — exactly like the core handlers. No DB connection in the realtime process. Cheap. Use this unless you have a reason not to.

2. **In-process (`frappe_context=True`).** Opens a full Frappe context for the handler body so you can call `frappe.has_permission(...)`, query the DB, etc. directly:

   ```python
   @realtime.on("project_subscribe", frappe_context=True)
   def project_subscribe(socket: Socket, project: str) -> None:
       if frappe.has_permission("Project", doc=project, ptype="read"):
           socket.join(f"project:{project}")
   ```

   Cost: **every such event** pays `frappe.init -> connect -> set_user -> commit/rollback -> destroy` and forces a DB connection into the realtime process. Use sparingly. The DB driver is forced to PyMySQL (the mysqlclient C extension would stall the gevent hub).

## Pushing events to clients (from the web process)

You do not emit from the web process directly — you publish through Redis, and this server bridges it to the connected sockets. `publish_realtime` is unchanged. There are named helper wrappers in `frappe.realtime`:

```python
from frappe.realtime import publish_to_room

publish_to_room("project:PROJ-0001", "project_updated", {"status": "Open"})
```

The room string you publish to must match the room your handler `join`ed.

### All helpers

Each is thin sugar over `publish_realtime` — same wire behavior, just named for the
target room. All take `*, after_commit=False` (defer the publish until the current
transaction commits) as a keyword-only option.

```python
publish_to_user(user, event, message=None, *, after_commit=False)
publish_to_doc(doctype, docname, event, message=None, *, after_commit=False)
publish_to_doctype(doctype, event, message=None, *, after_commit=False)
publish_task_progress(task_id, message=None, *, after_commit=False)   # note: no event arg
publish_to_website(event, message=None, *, after_commit=False)
publish_to_all(event, message=None, *, after_commit=False)
publish_to_room(room, event, message=None, *, after_commit=False)
```

Room mapping:

| Helper                  | Room                       | Reaches                                      |
| ----------------------- | -------------------------- | -------------------------------------------- |
| `publish_to_user`       | `user:{user}`              | all of that user's sockets on this site      |
| `publish_to_doc`        | `doc:{doctype}/{docname}`  | sockets subscribed to that document          |
| `publish_to_doctype`    | `doctype:{doctype}`        | sockets subscribed to that doctype           |
| `publish_task_progress` | `task_progress:{task_id}`  | sockets watching that task (fires `task_progress`) |
| `publish_to_website`    | `website`                  | every socket on this site                    |
| `publish_to_all`        | `all`                      | **System Users of this site** (not Guests)   |
| `publish_to_room`       | `{room}`                   | whatever room string you pass                |

`publish_to_all` is **site-scoped** (the `all` room = System Users of this site). It is
NOT the cross-site no-room broadcast that build events use — that path stays internal to
`publish_realtime`.

## Rules of thumb

- Keep handlers small and non-blocking in spirit — gevent yields on I/O (DB, HTTP, Redis), but tight CPU loops block the hub for every other socket.
- Never import `mysqlclient` / `MySQLdb` anywhere reachable from a handler. It is a C extension whose blocking socket cannot be monkeypatched and will stall the server.
- Room and event names are a shared contract with the browser client — keep them stable.
