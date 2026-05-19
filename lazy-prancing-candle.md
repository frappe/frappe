# Per-User Status in Frappe Framework — Specification & Plan

## Context

Frappe currently has no way to express "is this user reachable right now?". Apps that care — HRMS (leave, holidays, shift end), chat/inbox apps, assignment UIs — each invent their own ad-hoc presence. The goal is to add a single, first-class **User Status** primitive in the framework so apps can read it, set it, and react to it consistently. The Framework itself will also surface the status in places where users appear in the UI (navbar, avatars, assignment dialog, mentions, comments, timeline, sidebar viewers, list-view assignee chips).

Design decisions captured upfront (confirmed with user):
- **Storage:** two fields directly on the `User` doctype — `user_status` and `user_status_expires_at`. Nothing else.
- **Values:** fixed translatable enum (Select field). Custom statuses are out of scope for v1.
- **Conflict model:** none — last write wins. User and apps share the same setter.
- **Expiry:** every status carries optional `user_status_expires_at`; scheduler clears expired statuses.
- **Visibility:** any logged-in user can see any other user's status (broadcast via bootinfo, like `full_name` and avatar).
- **App API:** single whitelisted entry point `frappe.set_user_status(...)`.
- **Invisible mode:** included as an enum value; renders as "no dot".

---

## Goals / Non-goals

**Goals**
- A clean, translatable, cacheable representation of user availability on `User`.
- Python + JS APIs to read/write status.
- Realtime broadcast when status changes.
- Status indicator dot on every avatar surface in core (12+ locations).
- A status picker UX in the navbar user dropdown.
- A stable extension point for apps (HRMS, chat) without framework knowing about them.

**Non-goals**
- "Online / typing right now" presence. That stays with the existing socket viewers/typers; status is a *user-declared* or *app-declared* state, not real-time presence.
- Chat app inside Framework (chat was removed in v13).
- Per-doctype or per-document status overrides.
- Visibility/permission rules per status (status is broadcast to all logged-in users).
- Conflict resolution between user-set and app-set status. Last write wins; apps that misbehave are an app-policy problem, not a framework problem.
- Free-form status message (Slack-style "In a meeting until 4pm"). Can be added later as a 3rd field if demand emerges.

---

## Data Model — fields on `User`

Add to `frappe/core/doctype/user/user.json` (new section, e.g. between `Email Settings` and `Sidebar`):

| Fieldname                | Type     | Options / Notes                                                                                         |
|--------------------------|----------|---------------------------------------------------------------------------------------------------------|
| `user_status`            | Select   | `\nAvailable\nAway\nBusy\nDo Not Disturb\nOut of Office\nInvisible`. Empty = unset (renders as no dot). |
| `user_status_expires_at` | Datetime | When the status should auto-clear. Optional. Cron clears it.                                            |

Both fields are `read_only` on the standard User form (set via API/picker, not by editing the User doctype). `user_status` is `search_indexed` so list filters on it are cheap.

Why on `User` and not a separate doctype: user picked this. Pros: one row read for boot info; trivial to add to `user_info`; no extra permission machinery. Cons: User doc is already wide and saving it triggers heavy hooks — mitigated by writing via `frappe.db.set_value` with `update_modified=False` (same trick `sessions.py:update_last_active` uses today, see `frappe/sessions.py`).

---

## Backend API

Methods live on the `User` document class in `frappe/core/doctype/user/user.py` — no standalone whitelisted endpoint, no `frappe.set_user_status` re-export. Apps and the UI both go through the doc.

```python
class User(Document):

    @frappe.whitelist()
    def set_status(
        self,
        status: str | None = None,
        expires_at: str | datetime | None = None,
    ) -> dict:
        """Set this user's status.

        Behavior:
        - HTTP / request path: the caller can only operate on their own user
          record. Enforced at the top of this method.
          `frappe.session.user` if a request is in progress.
        - Server-side path (apps): instantiate the target user
          (`frappe.get_doc("User", target).set_status(...)`) and call directly.
          No request → no rebind, runs on whichever doc the caller chose.
        - `status` of `None` / empty clears both fields.
        - Last write wins.

        Returns `{status, expires_at}`.
        """
        if frappe.request and self.name != frappe.session.user:
            frappe.throw("Throw some error here")
        ...
```

The whitelist + the explicit `frappe.request` guard together honor "HTTP always means `frappe.session.user`": even if a malicious client points `run_doc_method` at `User/admin@x.com`, the call mutates `frappe.session.user`'s doc instead. Apps that legitimately need to set another user's status always go through `frappe.get_doc("User", x).set_status(...)`, which has no `frappe.request` and is not affected.

A small module-level helper stays in `user.py` for the scheduler:

```python
def expire_user_statuses():
    """Scheduled — clear statuses whose expires_at has passed."""
```

### Server-side controller integration

Also in `User` (same file):
- `before_save`: if `user_status_expires_at` is in the past at save time, blank both fields. (Defensive; the scheduler is the primary cleaner.)
- Typed annotations for the two new fields (the codegen pattern at `user.py:88–115`).
- The realtime broadcast and cache invalidation happen inside `set_status`, after the DB write commits.

---

## Realtime Broadcast

Inside `User.set_status`, after the DB write commits:

```python
frappe.publish_realtime(
    event="user_status_change",
    message={"user": user, "status": status, "expires_at": expires_at},
    after_commit=True,
    # No `user=` / `room=` → broadcast to "all" site room.
)
```

Broadcast to `get_site_room()` (all desk sessions) — matches the visibility decision. Pattern mirrors `notification_log.py:37`.

Frontend subscribes once in `frappe/public/js/frappe/desk.js` (post-bootinfo):

```javascript
frappe.realtime.on("user_status_change", ({ user, status, expires_at }) => {
    if (frappe.boot.user_info[user]) {
        Object.assign(frappe.boot.user_info[user], {
            status, status_expires_at: expires_at,
        });
        frappe.user_status.refresh_indicators(user);  // see UI section
    }
});
```

---

## Caching

Follow the `get_users_for_mentions` pattern (`frappe/desk/search.py:411–421`):

- `User.get_status` uses `frappe.cache.get_value(f"user_status:{self.name}", generator, expires_in_sec=300)`.
- `User.set_status` calls `frappe.cache.delete_key(f"user_status:{self.name}")` after writing.
- Add `"user_status:"` prefix to the per-user cache invalidation list in `frappe/cache_manager.py:user_cache_keys` so that any cache flush on a user (e.g., `frappe.clear_cache(user=...)`) wipes the status cache too.
- **User info surfacing**: bootinfo only ships current user (`boot.py:357` calls `add_user_info(frappe.session.user, ...)`); other users are loaded lazily through `frappe.utils.add_user_info` (`frappe/utils/__init__.py:1094`). Extend the `frappe.get_all("User", ...)` query there to also fetch `user_status` and `user_status_expires_at`, add them to the `_UserInfo` TypedDict, and include them in the `setdefault().update(...)` block. No change to `boot.py` needed.

---

## Hooks & Extensibility for Apps

One new hook point in `frappe/hooks.py`:

```python
# Fired AFTER a status change has been persisted and broadcast.
# Signature: (user: str, old: dict, new: dict) -> None
user_status_change = []
```

App authors do **not** need to register status providers — they instantiate the target user and call `set_status` from their own existing doc_events. Example for HRMS (not in this repo, doc'd for completeness):

```python
# in hrms/hooks.py
doc_events = {
    "Leave Application": {
        "on_submit": "hrms.leave.handlers.set_out_of_office_status",
        "on_cancel": "hrms.leave.handlers.clear_out_of_office_status",
    }
}

# in hrms/leave/handlers.py
def set_out_of_office_status(doc, method):
    if doc.status != "Approved":
        return
    frappe.get_doc("User", doc.employee_user).set_status(
        status="Out of Office",
        expires_at=f"{doc.to_date} 23:59:59",
    )

def clear_out_of_office_status(doc, method):
    frappe.get_doc("User", doc.employee_user).set_status(status=None)
```

Server-side calls aren't running inside a `frappe.request`, so the session-user rebind in `set_status` doesn't trigger — HRMS modifies the employee's doc as intended.

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
        frappe.get_doc("User", user).set_status(status=None)
```

---

## Permissions

- `User.set_status` is whitelisted. Over HTTP it always operates on `frappe.session.user` — the `frappe.request` rebind at the top of the method makes the `dn` in the URL effectively cosmetic. A logged-in user can therefore only ever change their own status via the API.
- Server-side callers (apps) bypass the rebind because there is no `frappe.request`. They are trusted Python code; if HRMS chooses to call this on any user, that's its prerogative.
- Reading status: anyone logged in can read via `User.get_status` (broadcast in bootinfo anyway).
- No new permission rule entries on the User doctype — the new fields are `read_only` in UI and gated by the method.

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

Wire via `frappe.client.run_doc_method`:

```javascript
frappe.xcall("frappe.client.run_doc_method", {
    dt: "User",
    dn: frappe.session.user,
    method: "set_status",
    args: { status, expires_at },
}).then(({ message }) => { /* dialog close */ });
```

(`dn` is `frappe.session.user` for clarity, but per the backend rebind it would be honored even if blank.) New JS file: `frappe/public/js/frappe/ui/toolbar/user_status_dialog.js`.

### 3. User profile page

Show the status badge at the top of `frappe/core/doctype/user/user.js` profile view, plus an edit shortcut that opens the same picker.

### 4. List view status filter

Adding `user_status` as `in_standard_filter` on the User doctype gives list filters for free (no JS change needed).

---

## Migration / Patches

Adding fields to a core doctype is handled by the regular `bench migrate` sync — no patch needed. The fields default to NULL, which renders as "unset" and is the correct initial state.

---

## Files to be Modified / Added

**Modified**
- `frappe/core/doctype/user/user.json` — add 2 fields + put them in a collapsible section.
- `frappe/core/doctype/user/user.py` — type hints; `before_save` expiry guard; new `User.set_status` / `User.get_status` methods; module-level `expire_user_statuses` for the scheduler; realtime broadcast + cache invalidation inside `set_status`.
- `frappe/hooks.py` — `scheduler_events.cron`, new `user_status_change` list.
- `frappe/utils/__init__.py` — extend `add_user_info` (and the `_UserInfo` TypedDict) to surface the 2 status fields whenever a user is lazily loaded.
- `frappe/cache_manager.py` — add `"user_status:"` to `user_cache_keys`.
- `frappe/public/js/frappe/utils/common.js` — wrap `get_avatar` with status dot.
- `frappe/public/js/frappe/utils/user.js` — surface `status` from `frappe.boot.user_info`.
- `frappe/public/js/frappe/desk.js` — subscribe to `user_status_change` realtime event.
- `frappe/public/js/frappe/ui/toolbar/toolbar.js` + `navbar.html` — picker entry.
- `frappe/public/scss/desk/avatar.scss` — `.status-dot` styles.
- `frappe/translations/*` — pick up the new enum labels via standard extraction.

**Added**
- `frappe/public/js/frappe/ui/toolbar/user_status_dialog.js` — picker UI.
- `frappe/tests/test_user_status.py` — unit tests (set, clear, expiry, realtime, cache invalidation, session-user rebind for HTTP path).

Estimated diff size: ~350 LOC including tests (no new Python module needed — everything fits on `User`).

---

## Verification

End-to-end manual:
1. `bench --site test_site migrate` — confirm User doctype gains the two new fields.
2. `bench --site test_site console`:
   ```python
   frappe.get_doc("User", "user1@x.com").set_status(
       status="Out of Office", expires_at="2026-05-25 23:59:59"
   )
   frappe.get_doc("User", "user1@x.com").get_status()
   # → {"status": "Out of Office", "expires_at": ...}
   ```
3. Open desk in browser as a *different* user → user1's avatar should immediately show a purple dot (realtime). Hover → tooltip "Out of Office (until 25 May)".
4. As user1, set status to "Available" via the navbar picker → re-run the HRMS call, observe last-write-wins: HRMS overrides back to "Out of Office" with a fresh broadcast.
5. HTTP rebind check: logged in as user2, hit `/api/method/run_doc_method` with `dt=User&dn=user1@x.com&method=set_status&args={...}` → assert user1's row is unchanged and user2's status was set instead.
6. Wait past `expires_at` (or set 1-min expiry + run `bench execute frappe.core.doctype.user.user.expire_user_statuses`) → dot disappears within one scheduler tick.
7. Visit a form with a comment by user1, assign user1 to a task, and view a list with user1 as assignee → all three surfaces show the dot.

Automated:
- `bench --site test_site run-tests --module frappe.tests.test_user_status` covers: enum validation, scheduler expiry, cache invalidation, bootinfo payload, realtime broadcast (asserted via `frappe.publish_realtime` mock), session-user rebind on the HTTP path (mock `frappe.request` and assert the mutation lands on session.user not the requested `dn`).
- Existing test suites should pass unchanged; verify `frappe.tests.test_user` and `frappe.tests.test_realtime` are green.

---

## Risks & Open Questions

- **`Invisible` semantics.** "No dot" is indistinguishable from "no status set". Intentional — matches Slack. Document.
- **No conflict resolution.** A user setting "Available" while on approved leave will be re-stomped by HRMS on the next leave-related save (or vice versa, depending on order). Document as expected behavior; if real users complain, revisit with a `manual_status_until` field in a follow-up.
- **Bypass via direct field write.** Anyone with write access to `User` could change status by editing the User doc. Acceptable because System Manager already has full User access; mark fields `read_only` in UI to prevent accidental edits.
