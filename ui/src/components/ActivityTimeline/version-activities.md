# Smart Version Activities

Linear-style rendering of `Version` (field-change) history in the `@framework/ui`
ActivityTimeline. Goal: replace the legacy desk's run-on, value-dumping history
lines with scannable, value-aware, mergeable changes.

## Principle: dumb backend, smart frontend

- **Backend** (`activity.py`) ships each change as structured, already-translated
  data — it decides *what kind* of change it is and supplies the words, but does
  **no** layout, merging, or truncation.
- **Frontend** (`useActivityTimeline.ts` + `VersionItem.vue`) owns all
  presentation: same-field merging, before→after layout, value truncation.
- **Why the split:** merging is a cross-row decision and must re-derive on every
  reload/live update, so it lives in the frontend `computed`. Per-change content
  is independent, so it stays backend-translated (no new frontend i18n).

## Data shape (`VersionChange`)

Each change is one `VersionChange` — a discriminated union on `type` with exactly
two variants, because the renderer only ever asks one question: *does this row
hand me raw values to lay out, or a finished sentence to print?*

| `type` | used for | carries | renders |
|---|---|---|---|
| `diff` | scalar field changed (Status, Priority, link, date), or set from blank | `prefix`, `from?`, `to`, `history?` | `prefix` + `from` → `to`; **no arrow when `from` is absent** (set-from-blank) |
| `phrase` | long-text/HTML "updated Description", "cleared Owner", **and** doc-level submit/cancel/table rows | `text` | the phrase only |

Base fields on both: `name`, `fieldname?`. `fieldname == null` marks a doc-level
row (never merges) — it is **not** a separate type, since `phrase` + `fieldname`
already distinguishes field-notes from doc-events with zero duplication.

### Backend decision tree (`format_version_change`)
```
long-text fieldtype?     → phrase  ("updated X")
old present, new blank?  → phrase  ("cleared X")
old present, new present → diff    ("changed X" + from → to)
old blank,  new present  → diff    ("set X to" + to, no `from`)
not a single field?      → phrase  (submit/cancel/table rows, via format_docstatus_change)
```

## Merging (same-author sequences)

`groupVersionActivities` → `summarizeVersions` folds a consecutive same-author run
of version rows. Any non-version activity (comment/email/log) ends the run.

1. **Same field across saves** collapses to net `first.from → last.to`; every hop
   is kept in `history` (revealed by a chevron).
2. **No-op churn** (`from === to`, e.g. `H→B→C→H`) is dropped — no row.
3. **Survivors** of a run share one "+N changes" group row; a lone survivor
   renders inline.
4. **Identity** keys off the *first* row (stable as the run grows) so Vue reuses
   the component on re-derive instead of remounting and resetting expanded state;
   timestamp comes from the *last* row.

Merge eligibility is decided by `fieldname` presence (field-level → merges;
doc-level row with `fieldname: null` → stands alone), **not** by the `type` —
which is why field-notes and doc-events are functionally identical at render time
and both live under the single `phrase` type.

### Worked examples
| input | output |
|---|---|
| `status H→B→C→H` | *(nothing — net no-op)* |
| `status H→B→C→D` | `changed status H → D` (history: 3 hops, under chevron) |
| status B→H, priority→Low, type→Bug, status H→A | `+3 changes` → `status B → A` (history: 2 hops) / `set priority to Low` / `set type to Bug` |

## Rendering notes (`VersionItem.vue`)

- Values render as **bold text** (`font-semibold`), not pills.
- Arrow is a literal `→`.
- Group header: static "Show" + chevron (no Show/Hide swap).
- Change `history` revealed by a chevron, not "· N hops" text.
- **Truncation is frontend** (matches legacy desk convention): backend sends the
  full HTML-stripped value (`display_value`), `VersionItem` clips to 40 chars
  (via the shared `truncate` util) and shows the full value on hover via native
  `:title` only when clipped.
- Render path is text interpolation (`{{ }}`) → Vue escapes → no XSS, so
  `strip_html` (plain text) is correct; sanitize would be wrong here.

## Permissions

- `get_versions` does **not** filter fields — it returns the raw diff blob with
  every tracked field, including permlevel-restricted ones.
- `permitted = get_permitted_fields(doctype, ..., "read")` is the field-level
  permission authority; `is_field_visible` enforces it per change (plus
  `hidden`/`show_on_timeline`).
- Child-table fields get their own `get_permitted_fields(child_dt, parenttype=…)`.
- There is **no** native per-field "track this" allow-list — `track_changes` is
  doctype-level all-or-nothing; control is at *display* time (permission +
  `hidden`/`show_on_timeline`), not storage.

## Open decisions

- ~~**Rename `mode` → `type`** and collapse the type count.~~ **Done** — `mode`
  (`chips | set | text | raw`) is now `type` with **2 variants**: `diff | phrase`.
  `chips`+`set` → `diff` (arrow only when `from` present); `text`+`raw` → `phrase`.
  Settled on a render-shape pair (not a 3-way semantic split) because the
  field-note vs doc-event distinction is already carried by `fieldname == null`.
- Optional: per-phrase **icons** (submit ✓, +rows, cleared pencil) — would add an
  `icon?`/`kind?` to `phrase` rather than splitting the type.
- Optional: rename `format_docstatus_change` → `format_phrase_change`/`raw_change`
  (now used for table rows too, name is misleading).
- Optional: per-DocType timeline allow/deny filter in `is_field_visible`.

## Files

- `frappe/desk/form/activity.py` — `get_version_activities`, `format_version_change`,
  `format_docstatus_change`, `is_field_visible`, `display_value`, `LONG_TEXT_FIELDTYPES`.
- `ui/src/components/ActivityTimeline/types.ts` — `VersionChange`, `VersionActivity`.
- `ui/src/components/ActivityTimeline/useActivityTimeline.ts` — `groupVersionActivities`, `summarizeVersions`.
- `ui/src/components/ActivityTimeline/VersionItem.vue` — group/single wrapper + per-change diff/phrase renderer + field-history mini-timeline (folds the former `VersionChange.vue` / `VersionChangeHistory.vue`).

## Scope

Only consumers using `get_activity_timeline` (via `useActivityTimeline`) get this.
Consumers that hand-build their timeline (e.g. Helpdesk today) have no framework
`version` rows and would need to adopt the endpoint or replicate the shaping.
