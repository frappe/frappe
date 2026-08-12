# The icon-grid batch, and what ends it

The desk carries a retiring navigation surface — the icon grid — alongside the module-first
one. Everything that exists **only** because of that coexistence is listed here, and it is
removed in **one batch**, on **one call**, per line. This file is the call.

It exists because the previous round of "temporary" mechanisms — five overlapping ways to say
"this is mine" — became permanent by default. Nobody decided to keep them; nobody was ever
asked to end them. A written condition is what stops that happening twice.

**Addressed to a maintainer with fleet visibility.** Not to a site operator: nobody can
evaluate "the majority of sites" from one bench, and asking them to is how a condition becomes
nobody's job.

## The two triggers

| | `develop` / v17 | `version-16` |
|---|---|---|
| **trigger** | the backport has landed and the migration is proven | the Apps screen is set on the majority of sites |
| **the question it answers** | *is the new model right?* | *has the customer moved?* |
| **timing** | early, unconditional | open-ended, possibly years |

**No version ceiling on either line.** A version number fires whether or not customers moved,
which turns the invitation into theatre. The repo's `current + 2` convention protects app
authors against API breakage; the grid is not API — it is a screen behind a flag, whose data
survives the flip either way.

**One batch, not two clocks.** Carrying an inert, unread table costs approximately nothing. A
second removal call that someone has to remember is a real thing, and forgetting it is the
exact failure this file exists to prevent.

## The batch

Remove all of it together, on either trigger:

- `frappe/desk/doctype/desktop_icon/` — the grid's rows.
- `frappe/desk/doctype/desktop_layout/` — a user's arrangement of them.
- `frappe/desk/doctype/workspace_sidebar/` and
  `frappe/desk/doctype/workspace_sidebar_item/` — the inert archive the migration reads. It
  goes with the batch, not before: while it is here, a badly-migrated site can be migrated
  again from the same rows.
- `Desktop Settings.desktop_page`, `is_desktop_icons_page()` and its two call sites
  (`frappe/boot.py`'s `desktop_icons` payload and what `frappe/desk/desktop.py` renders at
  `/app/desktop`) — with the field gone, both collapse to the Apps path.
- `import_desktop_icon_fixtures` and the `Desktop Icon` entry in `APP_LEVEL_ENTITIES`
  (`frappe/model/sync.py`) — the icon fixture glob and its reaper entry.
- `seed_desktop_icons` (`frappe/desk/doctype/desktop_settings/desktop_settings.py`) — it
  exists only while the flag has two settings.
- The app-level fixture helpers **entirely** — `get_app_level_files`,
  `get_app_level_directory_path`, `create_directory_on_app_path` and
  `delete_app_level_folder` in `frappe/modules/utils.py`. Icons are their last caller: a
  sidebar exports per-module and rides the ordinary doc-files walk.
- `frappe/utils/new_navigation_nudge.py`, its boot key in `frappe/sessions.py` and
  `frappe/public/js/frappe/new_navigation_nudge.js` — there is nothing to invite anyone to
  once there is only one navigation.
- `frappe/desk/doctype/module_sidebar/convert_fixtures.py`, the
  `convert-sidebar-fixtures` command and
  `frappe/patches/v16_0/notify_apps_to_convert_sidebar_fixtures.py` — the remedy and the
  notice for app authors who have not re-exported.

## What was accepted, and what was rejected

**A condition has no forcing function.** *"Nobody evaluated it"* and *"not met yet"* look
identical from outside. That cost is accepted, on the record, rather than papered over.

Two mitigations were considered and rejected:

- **A release-checklist item** — it lives outside this repo, so it is a promise this codebase
  cannot keep.
- **Adoption telemetry** — engineering investment in a surface that eight separate decisions
  agreed not to invest in.

The mitigation that remains is this sentence, in this file, next to the list.

**A customer who declines the invitation is asked again in a later release**, not removed on a
date. Declining sets one `frappe.defaults` flag; a later release that wants to ask again
clears it. Nothing about the decline expires on its own.
