# Per-User Status in Frappe Framework — Specification & Plan

## Context

Frappe currently has no way to express "is this user reachable right now?". Apps that care — HRMS (leave, holidays, shift end), chat/inbox apps, assignment UIs — each invent their own ad-hoc presence. The goal is to add a single, first-class **User Status** primitive in the framework so apps can read it, set it, and react to it consistently. The Framework itself will also surface the status in places where users appear in the UI (navbar, avatars, assignment dialog, mentions, comments, timeline, sidebar viewers, list-view assignee chips).

Design decisions captured upfront (confirmed with user):
- **Storage:** `user_status` (Link → `User Status Type`) and `user_status_expires_at` (Datetime) on the `User` doctype.
- **Status taxonomy:** a separate `User Status Type` doctype is the master list. Each row has a user-facing `status_label` (e.g. "On Leave", "Working from Home") and a fixed `master_status` enum (Available / Away / Busy / Do Not Disturb / Out of Office / Invisible). The master controls rendering (dot colour, "Invisible" hiding); the label is what users see and pick.
- **Standard set:** six default User Status Types are seeded — one per master, named the same as its master. Apps extend the list with their own types (e.g. HRMS adds "On Leave" → master "Out of Office").
- **Conflict model:** none — last write wins. User and apps share the same setter.
- **Expiry:** every status carries optional `user_status_expires_at`; scheduler clears expired statuses.
- **Visibility:** any logged-in user can see any other user's status (surfaced lazily through `add_user_info`, like `full_name` and avatar).
- **Developer API:** `User.set_status` instance method on the User doc — **not** whitelisted. Apps call it via `frappe.get_doc("User", x).set_status(...)`. No permission check; trusted-caller.
- **UI / HTTP API:** separate whitelisted module function `set_status` — takes no user argument, always operates on `frappe.session.user`. No way over HTTP to set another user's status.
- **Invisible mode:** a master-status value; any type whose master is `Invisible` renders as "no dot".

---

## Goals / Non-goals

**Goals**
- A clean, translatable, cacheable representation of user availability on `User`.
- An extensible `User Status Type` master so apps can ship their own user-facing statuses without touching framework code.
- Python + JS APIs to read/write status.
- Status indicator dot on every avatar surface in core (12+ locations).
- A status picker UX in the navbar user dropdown.
- A stable extension point for apps (HRMS, chat) — both data-level (install their own Types) and event-level (subscribe to `user_status_change`).

**Non-goals**
- "Online / typing right now" presence. That stays with the existing socket viewers/typers; status is a *user-declared* or *app-declared* state, not real-time presence.
- Chat app inside Framework (chat was removed in v13).
- Per-doctype or per-document status overrides.
- Visibility/permission rules per status (status is broadcast to all logged-in users).
- Conflict resolution between user-set and app-set status. Last write wins; apps that misbehave are an app-policy problem, not a framework problem.
- Free-form status message (Slack-style "In a meeting until 4pm"). Can be added later as a 3rd field if demand emerges.
- Custom master statuses. The six masters are fixed (they encode dot colours / visibility). Apps add new *labels* on top of those six, not new masters.

---

## Data Model

### `User Status Type` (new doctype)

Lives at `frappe/core/doctype/user_status_type/`. Master list of user-facing status labels.

| Fieldname        | Type        | Options / Notes                                                                                                            |
|------------------|-------------|----------------------------------------------------------------------------------------------------------------------------|
| `status_label`   | Data        | Autoname (`field:status_label`). The user-facing string, e.g. "On Leave", "Working from Home". `reqd`, `unique`.            |
| `master_status`  | Select      | `Available\nAway\nBusy\nDo Not Disturb\nOut of Office\nInvisible`. `reqd`. Drives the dot colour and visibility.            |
| `enabled`        | Check       | Default `1`. Disabled types are hidden from the picker but still resolve for existing User rows (so we don't break tooltips).|
| `description`    | Small Text  | Optional. Shown in the picker as helper text.                                                                              |
| `icon`           | Data        | Optional Lucide icon name. Picker may render it next to the label.                                                         |

- `allow_rename = 1` — labels are user-facing strings and may need correcting. Renames cascade via standard Frappe link-rename machinery (User rows are updated automatically because `user_status` is a Link field).
- Translated doctype (`translated_doctype = 1`) so labels seeded by framework/apps participate in `__()` extraction.
- Permissions: System Manager has full CRUD; everyone with desk access has read (so the picker can list types). No write for non-System-Manager — apps install their types via `after_install` hooks or fixtures, not through HTTP.

### `User` (changes)

Add to `frappe/core/doctype/user/user.json` (new "User Status" section, between `Email Settings` and the next section):

| Fieldname                | Type     | Options / Notes                                                                                              |
|--------------------------|----------|--------------------------------------------------------------------------------------------------------------|
| `user_status`            | Link     | Options: `User Status Type`. Empty = unset (renders as no dot). `read_only` in UI. `search_indexed`. `in_standard_filter`.|
| `user_status_expires_at` | Datetime | When the status should auto-clear. Optional. Cron clears it. `read_only`.                                    |

Why a Link instead of a Select: extensibility. Apps add new types without patching the framework. Why on `User` and not a child table: one row read for `add_user_info`; one indexed column to filter on; trivial cache key.

Saving the User doc is heavy (hooks, validators, role re-evaluation). All writes from `set_status` use `self.db_set(..., update_modified=False)`, skipping those — same trick `sessions.py:update_last_active` uses today.

### Standard seed data

Six default User Status Types are created on install (one per master, named the same as its master). These cover the "vanilla" Slack-style picker out of the box. Apps add more via `after_install` (see Hooks & Extensibility).

---

## Backend API

Two entry points with different audiences. Both live in `frappe/core/doctype/user/user.py`.

### 1. `User.set_status` — developer API (instance method, not whitelisted)

Where the actual mechanics live. Apps call it server-side from doc_events, scheduled jobs, custom whitelisted methods, etc. No permission check — trusted-caller, same model as `frappe.db.set_value`. Cannot be invoked over HTTP (no `@frappe.whitelist()` decorator → `run_doc_method` will reject it).

```python
class User(Document):

    def set_status(
        self,
        status: str | None = None,
        expires_at: str | datetime | None = None,
    ) -> dict:
        """Developer API: set this user's status.

        Trusted-caller; no permission check. Not whitelisted — cannot be
        called over HTTP. Apps use it server-side:

            frappe.get_doc("User", "alice@x.com").set_status(
                "On Leave", expires_at="2026-05-25 23:59:59"
            )

        `status` is the *name* of a `User Status Type` (i.e. its label, since
        the doctype autonames from the label). End users do not call this —
        the navbar picker goes through the whitelisted `set_status` (below),
        which delegates here for `frappe.session.user`.

        - `status` of `None` / empty clears both fields.
        - Unknown / disabled types raise `frappe.DoesNotExistError`.
          (Disabled types are gated by the picker; if an app calls
          `set_status` with a disabled type that's its bug.)
        - Last write wins.

        Returns `{status, master, expires_at}` — the resolved master is
        included so callers don't have to re-fetch it.
        """
        old_status = self.user_status or None
        new_status = status or None
        master = None
        if new_status:
            # cached_doc keeps this cheap on repeated set_status calls
            type_doc = frappe.get_cached_doc("User Status Type", new_status)
            if not type_doc.enabled:
                frappe.throw(_("User Status Type {0} is disabled").format(new_status))
            master = type_doc.master_status
        self.db_set(
            {
                "user_status": new_status,
                "user_status_expires_at": expires_at or None,
            },
            update_modified=False,
        )
        frappe.cache.delete_key(f"user_status:{self.name}")
        for fn in frappe.get_hooks("user_status_change"):
            frappe.call(
                fn, user=self.name, old=old_status, new=new_status, master=master
            )
        return {"status": new_status, "master": master, "expires_at": expires_at or None}
```

### 2. `set_status` — whitelisted, UI / HTTP entry point

Thin wrapper. Takes no user argument: always operates on `frappe.session.user`. The navbar picker uses this. There is no HTTP-callable way to set another user's status — by construction, not by permission check.

```python
# module-level in frappe/core/doctype/user/user.py
@frappe.whitelist()
def set_status(
    status: str | None = None,
    expires_at: str | datetime | None = None,
) -> dict:
    """Whitelisted: set the current session user's status.

    Always targets `frappe.session.user`. Guests are rejected.
    """
    user = frappe.session.user
    if user == "Guest":
        frappe.throw(_("Guests cannot set a status"), frappe.PermissionError)
    return frappe.get_doc("User", user).set_status(status, expires_at)
```

A small module-level helper for the scheduler:

```python
def expire_user_statuses():
    """Scheduled — clear statuses whose expires_at has passed."""
```

### Server-side controller integration

Also in `User` (same file):
- Typed annotations for the two new fields (the codegen pattern at `user.py:88–115`).
- The DB write, cache invalidation, and hook fire all live inside `User.set_status` — single source of truth. The whitelisted module-level `set_status` and the scheduler both go through it. No `before_save` guard needed; expiry cleanup is the scheduler's job, and `set_status` writes via `self.db_set(..., update_modified=False)` which bypasses the heavy User save hooks.

---

## Propagation to other clients

No realtime broadcast. Status updates propagate via the existing `add_user_info` path: the next time another user's session loads info for this user (page render, lazy fetch when rendering a comment/mention/avatar), they get the current status. For the *current* user, the navbar picker updates the local `frappe.boot.user_info[frappe.session.user]` optimistically on success so the navbar dot reflects the new choice immediately.

Consequence: long-lived desk tabs may show stale status for other users until something triggers a re-fetch (navigation, list refresh, etc.). Accepted tradeoff for a v1 — realtime can be layered on later by publishing inside `User.set_status` and subscribing in `desk.js`, with no API change.

---

## Caching

- `User.get_status` caches `{status, master, expires_at}` per user for 5 min (`frappe.cache.set_value(..., expires_in_sec=300)`).
- `User.set_status` calls `frappe.cache.delete_key(f"user_status:{self.name}")` after the DB write.
- `clear_user_cache(user=...)` in `frappe/cache_manager.py` explicitly deletes `user_status:{user}` so any cache flush on a user wipes status cache too.
- **User info surfacing**: bootinfo only ships current user (`boot.py:357` calls `add_user_info(frappe.session.user, ...)`); other users are loaded lazily through `frappe.utils.add_user_info` (`frappe/utils/__init__.py:1094`). Extend it to also fetch `user_status` and `user_status_expires_at`, plus the resolved `user_status_master` via a LEFT JOIN to `User Status Type`. Add all three to the `_UserInfo` TypedDict and the `setdefault().update(...)` block. No change to `boot.py` needed.
- **User Status Type cache**: when a Type's `master_status` or `enabled` flag changes, every cached per-user `user_status` payload is stale. On Type save, clear the `user_status:*` namespace (one `delete_keys("user_status:")` call); types change rarely, this is cheap.

---

## Hooks & Extensibility for Apps

### Hook point

One new hook in `frappe/hooks.py`:

```python
# Fired by `User.set_status` AFTER the DB write and cache invalidation.
# Signature: (user: str, old: str | None, new: str | None, master: str | None) -> None
#   `old` / `new` are User Status Type names (e.g. "On Leave"), not dicts.
#   `master` is the master_status of the *new* type, or None if cleared.
#   `expires_at` is intentionally not exposed — consumers care about
#   availability transitions, not deadlines.
# Expected framework consumers: cache clearers (e.g. notification badge counts
# that depend on user availability). Apps that want to react to status changes
# should use this hook rather than monkey-patching set_status.
user_status_change = []
```

### Apps installing their own Status Types

Apps ship their statuses via an `after_install` (and ideally also `after_app_install`) handler that idempotently creates User Status Type rows. The framework provides a small helper `frappe.core.doctype.user_status_type.user_status_type.ensure_user_status_type(label, master, **kw)` that does an "insert-if-missing, update master if present" so app installs/migrations are safe to re-run.

Example for HRMS:

```python
# in hrms/install.py
def after_install():
    from frappe.core.doctype.user_status_type.user_status_type import ensure_user_status_type
    ensure_user_status_type("On Leave", master="Out of Office")
    ensure_user_status_type("Working from Home", master="Available")
    ensure_user_status_type("In a Meeting", master="Busy")

# in hrms/hooks.py
after_install = "hrms.install.after_install"
doc_events = {
    "Leave Application": {
        "on_submit": "hrms.leave.handlers.set_on_leave_status",
        "on_cancel": "hrms.leave.handlers.clear_on_leave_status",
    },
}

# in hrms/leave/handlers.py
def set_on_leave_status(doc, method):
    if doc.status != "Approved":
        return
    frappe.get_doc("User", doc.employee_user).set_status(
        "On Leave",
        expires_at=f"{doc.to_date} 23:59:59",
    )

def clear_on_leave_status(doc, method):
    frappe.get_doc("User", doc.employee_user).set_status(None)
```

`User.set_status` has no permission check — apps are trusted callers, same model as `db.set_value`. It is **not** whitelisted, so HTTP clients cannot invoke it directly: the only HTTP path is `set_status`, which is structurally limited to `frappe.session.user`.

Last-write-wins means HRMS can stomp a user's manual "Available" — that's by design. If a user with an approved leave really wants to look available, they re-set their status after HRMS sets it. Document this explicitly in the API docstring.

---

## Scheduler

Add to `frappe/hooks.py:scheduler_events` under `"cron"`:

```python
"0/15 * * * *": [  # every 15 min — same cadence as other lightweight sweeps
    "frappe.core.doctype.user.user.expire_user_statuses",
]
```

Implementation in `user.py` (module-level, since scheduler hooks point at dotted paths, not methods):

```python
def expire_user_statuses():
    expired = frappe.db.get_all(
        "User",
        filters={"user_status_expires_at": ("<", frappe.utils.now_datetime())},
        pluck="name",
    )
    for user in expired:
        frappe.get_doc("User", user).set_status(None)
```

---

## Permissions

- `User.set_status` is **not** whitelisted. It is a plain instance method, no permission check, trusted-caller model (same as `frappe.db.set_value`). HTTP clients cannot invoke it directly — `run_doc_method` rejects non-whitelisted methods. Apps and the scheduler use it server-side.
- `set_status` is the only whitelisted entry point. It takes no user argument, so structurally there is no way for an HTTP caller to set another user's status. Guests are rejected with `PermissionError`.
- Reading status: anyone logged in can read via `User.get_status` and via `add_user_info` (which surfaces status alongside name/avatar when a user is lazily loaded).
- No new permission rule entries on the User doctype — the new fields are `read_only` in UI and gated by the methods above.

---

## Frontend / UI

### 1. Avatar status dot — universal

Modify `frappe.get_avatar` and `frappe.avatar` in `frappe/public/js/frappe/utils/common.js:4–81` to optionally wrap output with a `<span class="avatar-with-status">` containing a `<span class="status-dot status-{slug}">` overlay. Drive entirely from `frappe.user_info(uid).status` — no caller changes needed for the 12+ surfaces already using `frappe.avatar`.

New SCSS in `frappe/public/scss/desk/avatar.scss`:

```scss
.status-dot {
    position: absolute;
    right: -2px; bottom: -2px;
    width: 10px; height: 10px;
    border-radius: 50%;
    border: 2px solid var(--card-bg);
    &.status-available    { background: var(--green-500); }
    &.status-away         { background: var(--yellow-500); }
    &.status-busy         { background: var(--red-500); }
    &.status-do-not-disturb { background: var(--red-700); }
    &.status-out-of-office  { background: var(--purple-500); }
    &.status-invisible    { display: none; }
}
.avatar-xs .status-dot { width: 6px; height: 6px; }
.avatar-small .status-dot, .avatar-smaller .status-dot { width: 8px; height: 8px; }
```

Tooltip text: `{status}{" (until …)" if expires_at}`. Use Frappe's existing `data-bs-toggle="tooltip"` pattern.

This single change lights up every surface inventoried during exploration:
- form sidebar viewers/typers (`form_sidebar_users.js`)
- assignment sidebar + dialog (`form/sidebar/assign_to.js:283`)
- comment box (`form/controls/comment.js:18`)
- @mention dropdown (`form/controls/quill-mention/`)
- timeline messages (`form/templates/timeline_message_box.html`)
- like / share / follow widgets (`like.js`, `form/sidebar/share.js`, `document_follow.js`)
- list-view assignee group (`list/list_view.js:1149`)
- awesome-bar search results (`toolbar/search.js:330`)

### 2. Status picker — navbar user dropdown

Add a new menu item at the top of the `#toolbar-user` dropdown in `frappe/public/js/frappe/ui/toolbar/toolbar.js` and the template `frappe/public/js/frappe/ui/toolbar/navbar.html`:

```
[ ● Available  ▾ ]   "Set a status…"
```

Clicking opens a small dialog with:
- Radio/select list of the six enum values (with color swatch).
- Duration preset chips: `30 min`, `1 hour`, `4 hours`, `Today`, `This week`, `Don't clear`, plus a custom datetime input.
- "Clear status" button.

Wire via the dedicated whitelisted endpoint — no `dn`, no `run_doc_method`:

```javascript
frappe.xcall("frappe.core.doctype.user.user.set_status", {
    status,
    expires_at,
}).then((result) => {
    // Optimistic local update so the navbar dot reflects the change immediately
    // (no realtime broadcast — other clients pick this up on their next fetch).
    Object.assign(frappe.boot.user_info[frappe.session.user] ?? {}, {
        user_status: result.status,
        user_status_expires_at: result.expires_at,
    });
    /* dialog close */
});
```

The endpoint always operates on `frappe.session.user`, so there is no user/doc-name parameter to pass or spoof. New JS file: `frappe/public/js/frappe/ui/toolbar/user_status_dialog.js`.

### 3. User profile page

Show the status badge at the top of `frappe/core/doctype/user/user.js` profile view, plus an edit shortcut that opens the same picker.

### 4. List view status filter

Adding `user_status` as `in_standard_filter` on the User doctype gives list filters for free (no JS change needed).

---

## Migration / Patches

- Adding the new `User Status Type` doctype and the new fields on `User` is handled by the regular `bench migrate` doctype sync.
- A one-time patch `frappe/patches/v17_0/create_default_user_status_types.py` seeds the six standard types on already-installed sites. New installs get them through `after_install` (which calls the same helper). Both paths use the idempotent `ensure_user_status_type` so re-running is a no-op.
- The User row's `user_status` defaults to NULL → renders as "unset". No data migration needed.

---

## Files to be Modified / Added

**Modified**
- `frappe/core/doctype/user/user.json` — add `user_status` (Link → User Status Type) + `user_status_expires_at` (Datetime) in a new collapsible section.
- `frappe/core/doctype/user/user.py` — type hints; `User.set_status` (dev API: validates Type, resolves master, `db_set` + cache invalidation + hook fire); `User.get_status`; whitelisted module-level `set_status`; module-level `expire_user_statuses`; whitelisted `get_status_types` for the picker.
- `frappe/hooks.py` — `scheduler_events.cron`, new `user_status_change` list, `after_install` chain.
- `frappe/utils/__init__.py` — extend `add_user_info` (+ `_UserInfo` TypedDict) to surface `user_status`, `user_status_master` (LEFT JOIN to User Status Type), and `user_status_expires_at`.
- `frappe/cache_manager.py` — explicit `delete_key("user_status:{user}")` in `clear_user_cache`.
- `frappe/utils/install.py` — call `seed_default_user_status_types()` after the rest of install.
- `frappe/public/js/frappe/utils/common.js` — `get_avatar` reads `user_status` (label, for tooltip) and `user_status_master` (drives dot colour). `Invisible` master suppresses the dot.
- `frappe/public/js/frappe/utils/user.js` — surface status fields from `frappe.boot.user_info`.
- `frappe/public/js/frappe/ui/sidebar/sidebar_header.js` — picker entry in the workspace dropdown.
- `frappe/public/js/frappe/ui/toolbar/user_status_dialog.js` — picker fetches Types from `get_status_types`, groups by master.
- `frappe/public/scss/desk/avatar.scss` — `.status-dot` styles (per master).

**Added**
- `frappe/core/doctype/user_status_type/` — new doctype: JSON + controller + `ensure_user_status_type` helper + `seed_default_user_status_types` + `get_status_types_for_picker` whitelisted endpoint + tests.
- `frappe/patches/v17_0/create_default_user_status_types.py` — one-time seed for existing sites.
- `frappe/public/js/frappe/ui/toolbar/user_status_dialog.js` — picker UI (added in v1; updated in this revision).
- `frappe/tests/test_user_status.py` — unit tests, updated to use Status Type names + assert master resolution + assert disabled types rejected.

Estimated diff size: ~600 LOC including the new doctype and tests.

---

## Verification

End-to-end manual:
1. `bench --site test_site migrate` — confirm User doctype gains the two new fields.
2. `bench --site test_site console` — developer API path:
   ```python
   frappe.get_doc("User", "user1@x.com").set_status(
       "Out of Office", expires_at="2026-05-25 23:59:59"
   )
   frappe.get_doc("User", "user1@x.com").get_status()
   # → {"status": "Out of Office", "expires_at": ...}
   ```
3. Open desk in browser as a *different* user, navigate to any page that references user1 (e.g. a doc with a comment by user1) → user1's avatar shows the purple dot. Hover → tooltip "Out of Office (until 25 May)". (No realtime — the dot appears when `add_user_info` re-fetches user1, which happens on the page render.)
4. As user1, set status to "Available" via the navbar picker (which calls the whitelisted `set_status`) → navbar dot updates immediately (optimistic local update). Re-run the HRMS-style `get_doc(...).set_status(...)` call from console; user1 reloads and observes last-write-wins: status is back to "Out of Office".
5. **HTTP attack-surface check**:
   - `POST /api/method/frappe.client.run_doc_method` with `dt=User&dn=user1@x.com&method=set_status&args={...}` → expect HTTP 403/error: `User.set_status` is not whitelisted, so `run_doc_method` refuses to dispatch it. Confirm user1's row is unchanged.
   - `POST /api/method/frappe.core.doctype.user.user.set_status` as user2 → expect 200, but **user2's** row updates (not user1's). The endpoint has no user parameter, so cross-user mutation is not even expressible.
6. Wait past `expires_at` (or set 1-min expiry + run `bench execute frappe.core.doctype.user.user.expire_user_statuses`) → on next page render, the dot disappears.
7. Visit a form with a comment by user1, assign user1 to a task, and view a list with user1 as assignee → all three surfaces show the dot.

Automated:
- `bench --site test_site run-tests --module frappe.tests.test_user_status` covers: enum validation, scheduler expiry, cache invalidation, `add_user_info` payload includes the two status fields, `user_status_change` hook is fired with `(user: str, old: str | None, new: str | None)` (assert old/new are strings, not dicts), `set_status` (whitelisted module fn) targets `frappe.session.user` and rejects Guest, and **`User.set_status` is not whitelisted** — assert `frappe.handler` (or the dispatch layer) refuses to call it via `run_doc_method`.
- Existing test suites should pass unchanged; verify `frappe.tests.test_user` is green.

---

## Risks & Open Questions

- **`Invisible` semantics.** "No dot" is indistinguishable from "no status set". Intentional — matches Slack. Document.
- **No conflict resolution.** A user setting "Available" while on approved leave will be re-stomped by HRMS on the next leave-related save (or vice versa, depending on order). Document as expected behavior; if real users complain, revisit with a `manual_status_until` field in a follow-up.
- **Bypass via direct field write.** Anyone with write access to `User` could change status by editing the User doc. Acceptable because System Manager already has full User access; mark fields `read_only` in UI to prevent accidental edits.
