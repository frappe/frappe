# ActivityTimeline — expand to the framework's activity scope

## Current state (supersedes the plan below)

> This is the historical phased plan, kept as a record. Since it was written, the
> shape changed:
>
> - **One endpoint, not two.** The two-call data path (`get_docinfo` +
>   `get_version_timeline`) was unified into a single whitelisted
>   `frappe.desk.form.activity.get_activity_timeline` (new file
>   `frappe/desk/form/activity.py`) that returns a normalized, chronologically
>   ascending `Activity[]`. `load.py` no longer holds any timeline code.
> - **Thin composable.** All client-side parsing (DOMParser / plaintext /
>   `comment_type` bucketing) was deleted; `useActivityTimeline` is now a sorter
>   (sort → groupConsecutiveVersions → order) over one default-fetcher resource.
> - **Views are now IN scope.** "View Log" ships as an `audit` subtype `view`
>   ("{user} viewed this", gated by `track_views`) — the "Out of scope" note
>   below listing View Log is no longer accurate. (Milestone, Shared/Unshared,
>   web-page-views, `document_email`, and custom hook content remain out.)
>
> See `architecture.md` and `customization-api-summary.md` for the current state.

## Context

Reusable read-only `ActivityTimeline` component in `@framework/ui`
(`apps/frappe/ui/src/components/ActivityTimeline/`, branch `activity-area`). Given
`doctype` + `docname` it fetches `frappe.desk.form.load.get_docinfo` once and renders a
single merged chronological timeline.

**Today it renders only 3 of the framework's ~17 timeline item types**: emails
(`communications`), automated messages (`automated_messages`), comments (`comments`).
Every other activity type is **already in the `get_docinfo` payload we fetch** — we just
ignore the keys. Expanding scope = parse + render, no new endpoint (except Version diffs).

The framework (`form_timeline.js` / `base_timeline.js`) reduces almost every audit event to
a **Comment row** (one `frappe.get_all("Comment")` bucketed by `comment_type` in
`load.py: add_comments`) or a **Version row**, rendered as `{creation, content(HTML), icon}`.
That content is desk-specific HTML (Font Awesome `fa-lock`, `/app/...` links). We must NOT
`v-html` it — parse into **structured fields** and render with our own lucide icons.

## What the framework timeline shows

6 source doctypes: **Communication, Comment, Version, View Log, Milestone, User**.
Comment alone backs 10 rendered `comment_type`s: `Comment, Like, Info, Label, Edit,
Workflow, Assigned, Assignment Completed, Attachment, Attachment Removed`.
(Shared/Unshared render empty in core; Created/Submitted/Cancelled come from Version.)

## Scope

### Phase A — Comment-based audit logs (immediate)
All already in `docinfo`, all `comment_type` rows:
- `like_logs` → "{user} liked"  (lucide heart)
- `attachment_logs` → "{user} attached / removed {file}" + private lock  (lucide paperclip / trash-2)
- `assignment_logs` → "{user} assigned …" / "assignment completed"  (lucide user-plus / check)
- `workflow_logs` → "{user} → {state}"  (lucide git-branch)
- `info_logs` (Info/Label/Edit) → "{user} {text}"  (lucide info)
- doc-level **Created** + **Last edited** (read off the doc; not in docinfo — cheap fetch or defer)

### Phase B — Version field-changes (follow-up)

Render the field-change history: "{user} changed **Status** from **Open** to **Resolved**",
"added 1 row to Items", "submitted / cancelled this document". Source = the **Version**
doctype (`docinfo.versions`), already in the payload but currently ignored.

**Why this needs a backend, unlike Phase A.** A Version row stores raw JSON diffs, not text:
`data = { changed:[["status","Open","Resolved"]], added:[...], removed:[...], row_changed:[...] }`.
Turning that into a readable line needs two things a standalone frappe-ui app does not have:
1. **Field labels** — `"status"` → `"Status"` requires doctype metadata (`frappe.meta`).
2. **Field-level permission filtering** — desk skips changes to fields the user can't read,
   via `frappe.perm.get_field_display_status(df, null, frm.perm)` (returns Read/Write/None
   from the field's `permlevel` + the user's per-permlevel role perms, plus `hidden` /
   `show_on_timeline`). Doing this client-side would leak restricted field changes (e.g.
   "changed Internal Cost …" to a user without permlevel access). `frm.perm`/`frappe.meta`
   are desk-only constructs — absent in the SPA.

Desk does all this in `version_timeline_content_builder.js` (~430 lines). Do **not** port it.

**Approach — a whitelisted backend endpoint in frappe** (mirror CRM
`crm/api/activities.py: get_activities`), which runs where `frappe.get_meta()` and
`frappe.permissions` exist:
- New whitelisted method, e.g. `frappe.desk.form.load.get_version_timeline(doctype, name)`
  (or fold into a thin `get_activity_timeline` wrapper). `check_permission` on the doc first.
- For each Version: `json.loads(data)`, then for `changed` / `added` / `removed` /
  `row_changed`, look up each docfield via `frappe.get_meta(doctype).get_field(fieldname)`,
  resolve label, and **apply `get_field_display_status`** so restricted/hidden fields are
  dropped (port the exact filter from the JS builder).
- Handle `docstatus` transitions → "submitted" / "cancelled"; `created_by` + `updater_reference`
  → "created this via {DocType}"; `impersonated_by` / `audit_user` annotations.
- Return structured rows: `{ creation, owner, parts: string[], kind }` — frontend renders
  text, no `v-html` of server HTML where avoidable.

**Frontend:** add `VersionActivity` to the `Activity` union; fetch the version timeline via
a SEPARATE resource (parallel to get_docinfo) and merge into the same chronologically-sorted
list; render in a new `VersionItem.vue`.

**Backend permission filter (the key detail).** `get_field_display_status` is a JS-only
helper — the Python equivalent is `frappe.model.get_permitted_fields(doctype, user=...,
permission_type="read")`, which returns the set of fieldnames the user may read (already
encodes permlevel + role perms). Filter is a membership test: `if fieldname not in
permitted: skip`. Also skip `df.hidden and not df.show_on_timeline`. For `row_changed`,
use `get_permitted_fields(child_doctype, parenttype=doctype)`. NOTE: CRM does NOT field-filter
versions (only doc-level `has_permission`) — we are stricter, closing that leak.

`Version.data` shape (version.py:104): `changed:[[field,old,new]]`,
`added`/`removed:[[table,{dict}]]`, `row_changed:[[table,name,idx,[[field,old,new]]]]`,
plus `created_by` / `updater_reference` / `impersonated_by` / `audit_user`; `docstatus`
rides inside `changed` as `["docstatus", old, new]`.

**Runtime sequence (step by step):**
1. mount → `useActivityTimeline(doctype, docname)`.
2. composable creates TWO auto resources: A = `get_docinfo` (existing), B = `get_version_timeline` (new). Both fire in parallel.
3. A returns emails/comments/audit logs → `parseActivities` (existing; ignore A's raw `versions`).
4. B calls `get_version_timeline(doctype, name)`.
5. backend: `check_permission` → `permitted = get_permitted_fields(...)` → loop versions (limit 10), format+filter each diff → return `[{name, owner, creation, changes:[{field,old,new}]}]`.
6. B transform → `VersionActivity{ type:'version', key, timestamp, author, changes }`.
7. `activities` computed = merge(A.data, B.data) → sort (existing comparator) → `groupConsecutiveVersions` (fold runs of adjacent same-author versions into one; non-version item breaks the run).
8. `loading = A.loading || B.loading`.
9. `order` prop applied at display (existing `orderedActivities`).
10. template: `<VersionItem v-else-if="activity.type==='version'">`.
11. `VersionItem`: 1 change → inline; >1 → "Show/Hide +N changes from {user}" + chevron toggling a local `expanded` ref (no refetch).

New pieces: (1) backend endpoint, (2) `groupConsecutiveVersions` post-sort pass in useActivityTimeline, (3) `VersionItem.vue`. Everything else is wiring resource B into the existing flow.

Endpoint location: `frappe/desk/form/load.py` (alongside `get_communications`), whitelisted.

### Out of scope (note, don't build)
Shared/Unshared (empty in core), Milestone, View Log, web-page-views, `document_email`
link, custom hook content.

## Implementation (Phase A) — files under this directory

1. **types.ts** — extend `Docinfo` with `like_logs`, `attachment_logs`, `assignment_logs`,
   `workflow_logs`, `info_logs` (`DocinfoComment[]`). Add to `Activity` union:
   - `AttachmentLogActivity` — `{ action:'added'|'removed', fileName, fileUrl?, isPrivate, author }`
   - `AuditActivity` — `{ subtype:'like'|'assigned'|'assignment_completed'|'workflow'|'info', text, author }`
2. **useActivityTimeline.ts** — extend `parseActivities`:
   - `parseAttachmentLog(c)` — DOMParser the content: `<a>` text→`fileName`, `href`→`fileUrl`,
     `isPrivate = /fa-lock/.test(content)`. "Attachment Removed" = bare filename (no link).
   - generic audit parse (like/assigned/workflow/info) — build `text` from `author.fullname`,
     do NOT reuse desk-link HTML. Merge into the same sorted list.
3. **icons.ts** — add lucide icons (heart, paperclip, trash-2, user-plus, check, git-branch,
   info, lock). User wants `lucide-lock`, not `fa-lock`. Confirm lucide source available.
4. **AuditItem.vue** (new) — one-line row: lucide icon + text + (attachments) file link and
   conditional `<LucideLock>`. Structured props only, never `v-html`.
5. **ActivityTimeline.vue** — third gutter branch: small lucide icon for audit one-liners,
   render `AuditItem` in content column.
6. **index.ts** — export new public types.

## Verification
- `yarn build` in `apps/helpdesk/desk` (stay green).
- `http://replica.localhost:8080/helpdesk/new` — open a ticket with comment + private
  attachment + like; verify lucide icons, `lucide-lock` on private file, working link,
  attach/remove pairs, order matches desk form timeline.

## Workflow
Implement with `/opus`, review with fable. Keep this file's todos updated.

## Todo (Phase A) — DONE (build green; visual check on /helpdesk/new pending)
- [x] types.ts: extend Docinfo + AttachmentLogActivity / AuditActivity
- [x] useActivityTimeline.ts: parseAttachmentLog (DOMParser) + generic audit parse, merge & sort
- [x] icons.ts: LUCIDE_ICON_CLASS literal map (heart, paperclip, trash-2, user-plus, circle-check, git-branch, info, lock)
- [x] AuditItem.vue: structured one-line renderer (+ attachment link + lucide-lock)
- [x] ActivityTimeline.vue: third gutter branch (uses literal LUCIDE_ICON_CLASS map)
- [x] index.ts: export new types
- [x] helpdesk tailwind.config.js: scan ../../frappe/ui/src so shared-package classes generate
- [ ] visual check on /helpdesk/new vs desk form timeline

NOTE (JIT gotcha): lucide icons render via tailwind mask classes emitted ONLY when the
literal `lucide-<name>` string appears in scanned source. Dynamic `'lucide-' + name` is
invisible to the scanner → use the `LUCIDE_ICON_CLASS` literal map in `icons.ts`. Verified
all 8 classes present in built CSS.

## Todo (Phase B) — DONE (build green; runtime/visual check on a track_changes doc pending)
- [x] frappe: whitelisted `get_version_timeline(doctype, name)` in load.py — check_permission, parse Version JSON
- [x] backend: label lookup via `frappe.get_meta` + **`frappe.model.get_permitted_fields`** field-level perm filter (stricter than CRM, which doesn't field-filter)
- [x] backend: handle changed / added / removed / row_changed + docstatus (submit/cancel). created-via/impersonated/audit deferred.
- [x] types.ts: `VersionChange` + `VersionActivity` added to union
- [x] useActivityTimeline.ts: second resource (`get_version_timeline`) + `groupConsecutiveVersions` post-sort pass; merge both resources
- [x] VersionItem.vue: single change inline; >1 → "Show/Hide +N changes from {user}" collapsible (FeatherIcon chevron)
- [x] ActivityTimeline.vue: version branch + DotIcon gutter; index.ts exports
- [x] yarn build green
- [ ] runtime/visual check on a doctype with track_changes + version history (verify perm filtering)

NOTE: `row_changed` tuple order is `[fieldname, row_index, row_name, changes]` (per get_diff
in version.py:173) — the version.py docstring at line 113 has row_name/row_index SWAPPED.
NOTE: backend endpoint not executed (no bench run); imports verified present in load.py.

## Separate, still pending (not part of this plan)
HD Ticket Comment → core Comment migration patch
(`apps/helpdesk/helpdesk/patches/migrate_hd_ticket_comments_to_core.py`) — written;
attribution-repair run blocked by permission classifier, awaiting explicit go-ahead.
