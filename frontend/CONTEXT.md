# The desk layer (`frappe/frontend`)

The domain of desk v2's UI: the **shell** that the framework hosts at `/apps`, the
**URL space** beneath it, the **contributions** an app makes into it, and the **record
page** those contributions customize.

[`PHILOSOPHY.md`](./PHILOSOPHY.md) is the *rules*; this is the *vocabulary* those rules
use. [`CLAUDE.md`](./CLAUDE.md) is the operational half.

**One glossary.** A term means the same thing everywhere in this package. Where a word is
defined here, this file is canonical — a comment that disagrees is a bug in the comment.
Terms are in rough dependency order: hosting first, then contribution, then the record
page.

## Language

### Hosting and the URL space

**Shell**:
The single SPA the framework hosts, owning every URL beneath `/apps`. It owns everything
that must look the same in every app — the rail, the error states — and an app contributes
only *inside* a routed view. There is no shell-level hook of any kind.
_Avoid_: "the frontend" (ambiguous with the package), "shell story" (`ui/CONTEXT.md`'s
unrelated Storybook term).

**Prefix**:
The one bare path segment an app claims beneath `/apps` — `/apps/crm`, `/apps/desk`. An
app declares it with the `app_prefix` hook, or declares nothing and gets its own name.
_Avoid_: route prefix, mount point, base path.

**Claimed prefix**:
A prefix some active app actually answers for. Unclaimed is not an error: `/apps/nonsense`
is a *website* 404, not a shell 404, because the shell owns error states only **inside** a
claimed prefix.

**`shell_base`**:
The router's base as boot carries it — the **composed** path (`/apps/crm`), never the bare
segment. Composed on the server so the literal `/apps` never appears in JS.

**Slug**:
A doctype's address in a URL: `CRM Deal` → `crm-deal`. **The address, not the identity** —
canonicalisation always moves *to* the slug, never away from it.
_Avoid_: scrubbed name (`crm_deal`, the on-disk spelling used by contribution paths).

**Boot**:
A new, small per-prefix payload — deliberately *not* `frappe.sessions.get()`. Core boot
(the keys every prefix gets) plus app boot (the declaring app's contribution, merged
under core). `location.pathname` is its only input; the document carries nothing.

**`app_order`**:
The site's ordered array of **active** apps, used to order contributions. Deliberately not
`installed_apps` — that name is taken client-side for a permission-filtered list, and only
*ordering* fails silently.

**Generated route**:
One of the four routes every app gets with **no declaration at all** — home, list,
saved-view, record. `doctype` is a param, so four routes serve any number of doctypes.
There is no per-doctype route and no opt-out.
_Avoid_: default route, implicit route.

**Contributed route**:
A route synthesised from a `PageContribution`, named `page:<app>:<slug>`, and live only
for the declaring app. Contributed matches beat generated ones — `/deals` must beat
`/:doctype` — and they share one flat namespace.

**Rail**:
The shell-owned navigation strip that never disappears. It lists the doctypes the user can
**read** at this prefix — permission, not declaration.

**Manifest**:
The build's description of the one bench-wide bundle: `[{app, app_prefix, source_dir,
deps}]`, plus a separate wider `source_dirs` list covering *every* app on the bench.
An app is in the **bundle** only if it actually contributes source; every installed app
still gets a prefix and is still served.

**Singleton**:
A library that must exist exactly once in the bundle — `vue`, `vue-router`, `frappe-ui`,
`@framework/ui`, `reka-ui`, `dompurify`. Two apps disagreeing on one **fails the build**,
deliberately rather than letting a bundler silently pick a winner.

### Contribution

**Contribution**:
Something an app adds to the desk. The list is **closed**: if it is not in
`contributions/types.ts`, an app cannot do it. Not contributable, on purpose: a route
table, a doctype opt-out, shell chrome, a vite config, a boot key from JS.
_Avoid_: customization (that is the *effect*; a contribution is the delivery), plugin,
extension (see below).

**Kind**:
Which of the four contributions a file is — and a kind **is a path**, not a declaration:

| path | kind |
| --- | --- |
| `<module>/doctype/<scrubbed>/frontend/record.js` | record, owning app |
| `<module>/doctype/<scrubbed>/frontend/list.js` | list, owning app |
| `<module>/custom/<scrubbed>/record.js` | `custom` — a **foreign** doctype |
| `<module>/frontend/pages/<slug>.js` | a standalone page |

**Owning app**:
The app a contribution's doctype belongs to. Structural, needing no registry lookup: a
file under `doctype/<x>/frontend/` is colocated in the owner's own tree so it **is** the
owner's; a file under `custom/<x>/` is by construction somebody else's. Customizing a
foreign doctype does not move it into your prefix.

**Run order**:
Per doctype: the owning app first, then every other app in `app_order`. The rule is
*baseline first, more-specific intent last* — derived, not declared.

**Source**:
Who is speaking, for attribution and for removal. `host` is the app's own bundled code;
otherwise an app name, or `page-script:<name>`, or `builtin` for what the host seeded. A
source is the unit `unregisterSource` drops.
_Avoid_: `source_dir` (an app's on-disk path — unrelated), "layout source" (the object a
host feeds field overrides to — also unrelated). See **Words that collide**.

### The record page

**Record** (the page) vs **document** (the payload):
The page kind is a **Record** page; what it shows is a **document**, reached as `page.doc`
(the draft you edit) and `page.saved` (the document as the server last showed it). Two
deliberately separate words, neither may take the other's job — settled against renaming
the page to Document or Form in frappe/frappe#42212.
_Avoid_: Document or Form for the page; `page.record` (does not exist).

**`page`**:
The curated object every handler receives and imperatively mutates — a script's whole
capability surface. Nothing reaches a script except through it.
_Avoid_: form, frm, context.

**Surface**:
One customizable **region** of a Record page, whose verbs *record ops*; the rendered list
is those ops replayed over the host's built-ins. Four are true surfaces —
`quickActions`, `headerActions`, `tabs`, `panelSections` — sharing the verb set `add`,
`hide`, `show`, `update`, `move`, `has`, `order`. Two more, `fields` and `formTabs`, are
counted as surfaces and stage with them but are **not** `Surface`s: they override
properties rather than arrange items, and speak a strict subset with no `add`, `move` or
`order`.
_Avoid_: sections (`panelSections` and `Section` both already claim the word).

**Built-in**:
An item the host seeded rather than a script adding it, attributed to the source
`builtin` and folded in first. A script addresses one by name like any other item.

**Op**:
One recorded verb — `{verb, source, …}`. Ops are **recorded, not applied**; nothing is
rendered until a replay commits.

**Replay**:
The host clearing **every** surface and re-running **every** source in run order. This is
what makes conditional customization a plain `if` with no `else`. Ops stage while a replay
is open and the outermost commit publishes them in one flush.
_Avoid_: re-render, refresh (`page.refresh()`, the `onRefresh` event and the replay are
three names for one operation — prefer "replay" for the mechanism).

**Handler**:
One named function in the object a script exports — an event (`onRefresh`, `beforeSave`,
`afterSave`, `onTabChange`, `onFormTabChange`) or a **fieldname**. The event vocabulary is
closed; every other key is a fieldname, in one flat keyspace. A handler's arguments are
determined by its key: a top-level key gets `(page)`, one nested under a child table gets
`(page, row)`.

**Table handlers block**:
`products: { onAdd, onRemove, qty }` — the table is named once, and every key under it is
a child fieldname or one of the two lifecycle events. Flattened at registration to a
**dotted key** (`products.qty`), unambiguous because a fieldname cannot contain a dot.

**Page Script**:
A browser-authored customization stored in the `Page Script` doctype, evaluated as a real
ES module through a blob URL — so `export default {…}` is the same text as in a file
script, and bare imports resolve through the page's import map.
_Avoid_: Client Script (desk v1's doctype), Form Script (CRM v1's).

**Tier**:
The Page Script tier is the **last** in run order, after the host's file scripts and app
extensions, because it runs at page mount. A script that fails to load is skipped whole
and the rest of the tier still runs; a tier that could not be fetched is distinct from an
empty one.

**Field overlay**:
A script's per-field property override, applied at **render time** and never written into
the layout as authored, the `Form Layout` row, or doctype meta. Spelled in DocField
snake_case (`read_only`), not `FieldMeta` camelCase. Cleared by an ordinary replay.
Precedence: **permlevel is a hard floor a script cannot raise**; between the overlay and
`depends_on`, the overlay wins.
_Avoid_: field property (that is also what meta carries), `setFieldProperty` (v1's).

**Row handle**:
How a script addresses one child-table row: an object holding `(parentfield, key)` that
**re-finds its row on every access**, so a reorder is survived for free. An *address*, not
a write channel — fields are read and written bare, identically to writing through
`page.doc`.
_Avoid_: row proxy, `getRow` (both v1's, both position-capturing).

**Commit**:
The moment a field's control settles on a value — the firing point of a `<fieldname>`
handler. Per fieldtype at the widget, but one uniform rule at the engine, which never
branches on fieldtype. Not a keystroke and not a debounce, and **a programmatic write is
not a commit**: a cascade is authored, never ambient.
_Avoid_: change (the widget's spelling), input (per-keystroke, deliberately not offered).

**Read-only view**:
Every object `page` hands back is read-only, enforced by a lazy recursive proxy that
throws naming the path *and* the supported verb. `page.doc` and the row handle are the
only writable things it hands out.
_Avoid_: "frozen" (`Object.freeze` is shallow and names nothing in its error),
"immutable" (the underlying object is not — the *view* refuses writes).

**Tombstone**:
A removed `page` member kept for one major as a function that throws, naming the removal
and its replacement, then deleted. Deliberately **not** dev-gated, since a removal fires
on production sites.
_Avoid_: deprecation (implies a period of continued working).

## Words that collide

Recorded because the codebase genuinely overloads them. When writing a comment or a name,
reach for the unambiguous alternative.

- **`source`** — (a) who is speaking, for attribution; (b) `source_dir`, an app's on-disk
  path; (c) "layout source", the object a host feeds field overrides to. Three unrelated
  senses. Say *contributing source*, *source path*, or *layout source*.
- **`surface`** — (a) the `Surface` class, one customizable region; (b) the six members
  that stage together, two of which are not `Surface`s; (c) the loose sense in "the
  contribution surface", "the shell's own surface". Only (a) is a type.
- **`page`** — the curated `RecordPageApi`; a contributed standalone page; a Page Script;
  `ShellPage`, the server renderer; and desk v1's `Page` doctype. Qualify it always.
- **`record`** — the page kind; the contribution kind and filename; a docname field in the
  error reporter; **and a verb** (`Surface.record`, private, "verbs record ops"). No
  *exported* API may use it as a verb — say `push` or `append`.
- **`tier`** — a customization tier (`page_script | extension | file_script`); the
  per-doctype set of loaded Page Scripts; and "the declarative tier" for `page.dialog.form`.
- **`name`** — a `SurfaceItem`'s address; a route param meaning docname; a `PageScriptRow`
  name; and `PageFormTab.name`, which is explicitly *not* the address — that is `identity`.
- **`actions`** — the contribution type's bag of `{name, label, run}`; dialog buttons; the
  default group a header item lands in; and, loosely, quick actions.
- **`prefix`** and **`claim`** — a URL prefix an app claims, versus a dotted-path prefix in
  the compatibility guard, versus a header item's recorded anchor claim.

**One live inconsistency, not a collision:** the header surface is `page.headerActions` in
code, while "header" unqualified names the *rendered* region (`HeaderControl`, `HeaderBand`,
`HeaderProjection`). A decision to rename the surface to **`page.header`** and its item type
to `HeaderItem`, adding a `zone: 'left' | 'right'` key, is settled but **not implemented**
— see frappe/frappe#42271. Until it lands, write `headerActions` for the surface.

## Example dialogue

— "My app's `record.js` for Contact isn't running. It's at
`myapp/mymodule/custom/contact/record.js`."
— "That path is right — it's a `custom` **kind**, so Contact stays in its own **prefix**
and your handlers just join its **run order** after the **owning app**. Check the console:
a contribution with no default export is dropped with a warn, never a throw."

— "It runs, but my `page.fields.hide('phone')` does nothing on some records."
— "**Field overlay** is a render-time overlay and **permlevel is a hard floor** — but hide
should work regardless. More likely the **replay**: every source re-runs from scratch each
time, so if a later source shows it, the last write wins."

— "Can I read the value before the user's edit?"
— "`page.saved` — the **document** as the server last showed it. `page.doc` is the draft."
