# What `page` promises

The compatibility policy for the Record page customization API — the `page` object
every handler receives. Two audiences program against it, and they carry very
different risk:

- **File scripts** are contributions compiled into the shell's own bundle. They are
  rebuilt with the host, so a break is caught at build time by the person who caused
  it. Cheapest to break.
- **Client Scripts** are text stored in a site's database, as `Client Script` rows with
  `view = Record`. Nobody rebuilds them. They survive every upgrade, on sites with no
  developer watching. The audience that pays for a break.

What `page` offers, verb by verb and region by region, is in [`SCRIPTING.md`](./SCRIPTING.md);
this document says what of it survives an upgrade.

## Start with the version reality

The engine lives in `frontend/src/recordPage/` on the `desk-v2` branch, which is not yet
released. Two of the four shared dependencies a script may reach — `frappe-ui` and
`@framework/ui`, at version `0.0.0` — carry no stability guarantee at all.

So this document does not make a guarantee. It states an **intent**: which parts of
`page` are designed to outlive the implementation underneath them, which parts are
explicitly not, and how you find out when one moves. Everything below should be read
in that voice.

## The stable idea: verbs and events

What `page` is _for_ is a small, closed vocabulary:

- **Seven surfaces** — `quickActions`, `header`, `tabs`, `panelSections`, `frame`, `body`,
  `form` — each speaking the same **seven verbs**, `add`, `hide`, `show`, `update`, `move`,
  `has`, `order`, and `clear`. `form` is the Details form as one list, its sections the
  built-ins and a script's parts between and beside them, so a part sits at a neighbour's
  grain: a cell beside a field, a block beside a section.
- **Two overlays, `fields` and `form.tabs`**, speaking a strict subset of them — `hide`,
  `show`, `update`, `has`, `get`, and on `form.tabs` alone `clear`. The subset is the point: the seven arrange items
  a script may also create, while these are authored elsewhere and a script only
  overrides their properties, so there is no `add`, `move` or `order` to mean anything.
  For `fields` the author is the DocType; for `form.tabs` — the **Form Layout tabs**, the
  strip inside the record's details tab — it is the administrator editing the layout, and
  a tab there is a container of *fields*, so an `add` would have to invent fields. That is
  `page.dialog`'s job, and a whole custom view belongs on the record strip, `page.tabs`.
  On both overlays a script **beats `depends_on` in both directions**:
  `hide()` closes a tab the condition opened, `show()` opens one it closed. On `form.tabs`,
  `update` takes a **`label` and nothing else**: rewriting the administrator's `depends_on`
  expression is not a script's to do, and a script wanting conditional visibility already
  has a real `if` in `onRefresh`. `form.tabs` additionally carries two members `fields` has
  no use for — `active` and `activate` — for the plain reason that a strip has a reader
  standing on it and a field list does not. What the subset excludes is **arrangement**,
  not reading or navigation. `fields` is one overlay over every place a field is drawn:
  the same patch reaches the Details form and the Side Panel layout, which is why an
  insert beside a field lives on `form` and not here.
- **Two tab surfaces, and they are not interchangeable.** `page.tabs` means the **record**
  strip — activity, emails, files, details — and always will; `page.form.tabs` means the
  Form Layout strip *inside* details, a child of `page.form` because everything about the
  Details form sits under that one object. `page.tabs.active` returns a tab's **name**,
  because those tabs are named by whoever wrote them; `page.form.tabs.active` returns an
  **identity** — a resolved address — or `''` when the reader is not in the form. The
  asymmetry is real; do not assume one from the other. An identity is **safe to store in a
  script**: a Form Layout is named when it is *saved*, once and for good, so renaming a
  tab's label or dragging an unlabelled one leaves its address alone. It reads as an
  identity rather than a name because `FormLayout` resolves it itself — it renders in
  dialogs too, where nothing has named the tabs — not because an administrator's tab might
  be nameless. It no longer can be. The strip had a top-level name before it was placed
  under `form`; that spelling is gone, with no alias, because it never reached a release.
  `onFormTabChange` keeps its name: it names the event, not the surface.
- **`activate(name)` moves the reader; it and the panel's `open`/`close` are the only verbs
  that act rather than arrange.** Both tab surfaces carry `activate`, each addressing its
  own strip and no other — `page.tabs.activate('emails')`,
  `page.form.tabs.activate('shipping')`. It is a **verb and not a writable `active`** on
  purpose: `active` is *derived* from what the strip can currently show, so a script that
  assigned a hidden or unknown name would read back something it never wrote. A verb can
  say so instead. Naming a tab that is hidden, unknown, or on the other strip **warns in a
  development build and does nothing** — activation does not reveal a hidden tab, because
  `show()` is already the verb for that, and one act should not quietly perform two. The
  name resolves against the strip as it stands at the moment of the call: an activation
  fired before the tab exists misses, and is not queued. Called from `onRefresh`, it
  resolves against the strip that replay is building — a tab the same handler just
  added is a tab it can move to — and the reader arrives once the replay has settled,
  because until then the strip on screen is still the last one. A tab that leaves the
  strip before it settles is a miss, and warns like one.

  Two things follow from *moving the reader* that reading `active` never had to worry
  about. On `page.tabs`, `active` on the next line reads the new tab, except inside a
  replay, where the move waits for the commit. On `page.form.tabs` a **hit is not
  synchronous**: the move goes through the form's own navigation, so `active` on the
  next line still reads the tab you left — read it in the next handler. And a move
  **fires the strip's change event**, since `onTabChange` and `onFormTabChange` fire on
  any cause once the page has painted; `activate` is the first verb that lets a handler
  cause the event it is handling, so activating from inside one is yours to make
  terminate.
- **The whole header row is one flat list.** A `header` item carries `zone`: `'left'`
  puts it among the crumbs, and omitting it — the default — puts it on the right, with
  the controls and `⋯`. The crumbs and `Save` are ordinary built-in items on that list,
  named `doctype`, `record` and `save`, so `update('record', { label })` renames the
  title crumb and `hide('save')` removes the button, as desk v1's `disable_save` does.
  An item's place within its zone is its place in the one list; `zone` is a patchable
  key like any other, so `update('favourite', { zone: 'right' })` relocates an item.

  A `header` item also carries `display`. On the right, `'button'` gives it a top-level
  button of its own, `'dropdown'` gives it a top-level dropdown button of its own,
  `'section'` gives it a titled band, and omitting it leaves it an ordinary entry in the
  shared `⋯`. On the left, `'crumb'` draws it as a breadcrumb — linking to `href` when
  one is given, running `run` when that is — and omitting it gives a button, since the
  left has no menu to default into. `zone` and `display` are orthogonal.

  A `dropdown` and a `section` are **containers**: ordinary, addressable items that carry
  the label and the icon, differing only in when their members are visible — a dropdown
  hides them behind a trigger, a section shows them under a grey title. So
  `hide('telephony')` removes the whole control, members and all, however deep they sit,
  and a container is placed by **its own** position, never by its first member's.

  **`group` has one meaning: _put me inside the item named this._** If an item of that name
  is declared, you get what it declares; if nothing of that name exists, the engine
  synthesises an **anonymous, untitled container** — the adjacency band inside `⋯` that an
  omitted `group` (meaning `actions`) has always given. So **a band shows a heading iff its
  container is declared**, and a script that never declared one never grows headings.

  ```js
  page.header.add({ name: 'refresh_quote', label: 'Refresh Quote', display: 'button' })
  page.header.add([
    { name: 'telephony', label: 'Telephony', display: 'dropdown' },
    { name: 'call', label: 'Call customer', group: 'telephony' },
    { name: 'danger', label: 'Danger', display: 'section', group: 'telephony' },
    { name: 'wipe', label: 'Wipe call log', group: 'danger' },
  ])
  ```

  **The list you write stays flat; only the rendering nests.** A container that points at
  another container renders inside it — a dropdown as a submenu, a section as a titled band
  — so every item keeps one name and `hide`, `move` and `order` still reach all of them.
  Nesting stops at **two containers**: deeper, and a `group` cycle, are clamped to the
  deepest level they can reach and warned about in a development build. A container never
  runs — its `run` warns and does nothing; the items inside it run.

  A section's `icon` is part of the item — it is what makes the section
  addressable, and `update('danger', { icon })` works like any other — but the
  heading it renders as has no room for one, so **an icon on a section is not
  drawn**. Nothing else about it is different.

  **`add` also takes an array**, which splices as a unit at the anchor, in list order. It
  is the same flat list either way: you still repeat `group` on each member, because
  indentation is not scope and names are one namespace per surface.

  **Position orders items only within one rendering.** An anchor naming an item that
  renders somewhere else still splices exactly where it always did — and warns in a
  development build, because the author asked for "after Refresh Quote" and the reader got
  "below Delete". The left zone is a rendering of its own, so an anchor across the two
  zones warns the same way.
- **`page.frame` is the column as one list.** Its two built-in regions, `header` and
  `body`, and its one item key of its own, `gutter`, are the three names a script may
  lean on; they are kept for a major. A band is placed by `before`/`after` naming a
  region or another band, and two scripts adding at one place are ordered by run order,
  then by position. `move` on a built-in warns in a development build and does nothing.
- **`page.body` is the body row as one list.** Its two built-in columns, `form` and
  `panel`, and its column keys of its own — `width`, `minWidth`, `maxWidth`,
  `collapsible`, `gutter` — are the names a script may lean on; they are kept for a
  major. The keys are engine words, read and dropped from the item, not props forwarded
  to the component. A column with no `width` flexes; one with `width` is fixed and the
  reader's remembered width and collapsed state win over it. The seven verbs and `clear`
  all work on the built-ins. What the host does on a narrow screen is not observable from a script.
- **How many top-level controls fit is the host's business, and a script cannot observe
  it.** An item that does not fit is **demoted into `⋯`**, keeping its own band ahead of
  the built-ins and in the order it asked for; a dropdown collapses whole, under its label.
  A submenu inside it survives the collapse and a **section inside it loses its title**,
  which is one more thing demotion is lossy about and nothing to branch on.
  That is `add`'s promise — that the item is *reachable* — being kept, so there is no
  signal and nothing to branch on: `visible()` means *not hidden*, never *on screen where
  you asked*. A dropdown whose members are all hidden is a button that opens nothing, so it
  neither renders nor takes up room, while staying addressable. Which item loses is stated
  over the one flat order — the last one loses first — so `order()` and `move()` are the
  priority knob and there is no `priority` key. A promoted built-in
  (`update('delete', { display: 'button' })` is allowed, like any other update) is ordered
  and demoted by that same rule, with no exception for where it came from.
- **`Save` is an item like any other, and the last built-in on the list.** A new item
  with no anchor appends after it; `add(item, { before: 'save' })` is how a button sits
  to its left. It is ordered and demoted by the fitting rule with no exception, and the
  host alone decides that it is disabled while nothing has changed.
- **A closed event list** — `onRefresh`, `beforeSave`, `afterSave`, `onTabChange`,
  `onFormTabChange`, `<fieldname>`, and a child table's own family, written **nested under
  the table's fieldname**: a handler per child field, plus `onAdd` and `onRemove`.

  ```js
  export default {
    onRefresh(page) {},
    status(page) {},
    products: {
      onAdd(page, row) {},
      onRemove(page) {},
      qty(page, row) {},
    },
  }
  ```

  Internally these are one flat keyspace — `products.qty`, `products.onAdd` — joined
  on the one character a Frappe fieldname structurally cannot contain, so a child
  field can never collide with a parent one. **Every event name in that keyspace is
  `on`-prefixed or camelCased for one reason**: the alternative is a legal fieldname.
  `products.add` would be the same string as the commit event of a child field called
  `add`, and `refresh`, `before_save` and `after_save` are all spellings a real field
  can carry — which is why the top-level keys read `onRefresh`, `beforeSave`,
  `afterSave`, `onTabChange`. Those four were respelled from snake_case as a **hard
  break**: the old spellings are now unknown keys, warned about once and never fired.
  Dual-accepting both would have put the collision back permanently.

  The `on` prefix is a convention rather than a guarantee — no fieldname *has* to be
  lowercase — so a child doctype carrying `onAdd` or `onRemove` is warned about by name
  at load, **in a development build**. Where it collides, editing that field on a row
  fires the table's lifecycle handler: the hole is announced, but it is a misfire, not
  an inert gap.
- **Both tab events fire on a change, never on arrival.** A tab event means the active tab
  *changed* — by a click, by a script hiding the tab the reader was on, or by a `depends_on`
  condition taking it away. It does not fire on first paint, and a strip that is torn down
  and rebuilt is a first paint again: returning to the details tab restores where the reader
  was without announcing it, because that move is the *record* strip's and `onTabChange`
  has already reported it. A script that wants the tab on load reads `page.form.tabs.active`
  in `onRefresh` while the reader is on Details — which is what "state lives on `page`" is
  for.
- **One rule for a handler's arguments: its key decides them.** A top-level key gets
  `(page)`; one nested under a table gets `(page, row)`, except `onRemove`, whose
  row is gone. The row is an address, not a payload — `page.rows('products')`
  hands you the same handles in any handler at all.
- **A handful of contracts**: every `page.dialog` verb resolves `null` when the reader
  dismissed the dialog, so `if (!result) return` is always the idiom; a throw in
  `beforeSave` blocks the save; a handler that throws is isolated, half-applied, and
  does not take other scripts down with it.

These are deliberately small, closed, and shaped like frappe rather than like the
component library beneath them. They are what we would fight hardest to preserve.

## The line: `page` never passes your options through

The important half of this policy is not the verb list. It is the boundary between
`page` and the unstable things reachable _through_ it.

**The rule: no `page` verb forwards an options object, a nested option shape, or a
callback argument straight to a dependency.** Everything a script hands `page` is
picked apart by the engine and forwarded key by key; everything the engine hands a
script's callback is the engine's own object.

There is one shaped hand-through, and it is shaped on purpose. A header item's `props`
goes to whatever draws the item, and only to the props that thing declares:

- a control in the row (a button, a dropdown trigger, `Save`) is drawn by frappe-ui's
  `Button`, so `props` is filtered to `Button`'s declared props;
- a row in a menu is drawn by the menu option, so `props` is filtered to the option's
  declared keys;
- an item with its own `component` is drawn by that component, and its `props` are not
  filtered, because the engine cannot know what a component it did not write declares.

**The line: the engine forwards a frappe-ui component's public declared props where
that component draws the item, and frappe-ui carries the deprecation of a renamed
prop.**

The line moved here from a stricter one, and the reason is the version reality above.
After frappe-ui v1 its props lock, and a renamed prop keeps its old spelling for a time
before it goes. So the change a stored script could not see, a prop whose meaning moves
under it, is frappe-ui's to announce and phase out, not the engine's to intercept. The
engine adds no word of its own for emphasis, a tooltip or a disabled state; a script
says `variant: 'solid'` in `Button`'s spelling and reads `Button`'s deprecations.

The trade is plain. A new prop frappe-ui declares on `Button` does reach a script's
`props` without anyone adding it to `page`, so "frappe-ui got better" now moves a
script's reach along with it. What a script gets for that is a vocabulary it can look up
in frappe-ui's own documentation. What the engine keeps is the boundary: a key the
drawing component does not declare is **dropped, with a dev-mode warning** naming the
source, the item and the key. It does not silently do nothing. `class` is allowed on a
`Button` control, since it reaches the button as an attribute; `style` is not. `label`
and `icon` belong on the item, and a copy inside `props` is refused with the same
warning.

The engine owns no list of frappe-ui's props. The host reads `Button`'s declared props
off the component, hand-lists the menu option's keys, and hands both to the engine, the
way it hands the icon source. Every other `page` verb keeps the old rule: a key `page`
does not read is dropped, with a dev-mode warning naming it.

### What that means for the header's menus

The header renders through frappe-ui's `Menu`, which offers a good deal more than
`display` and `group` do. Two questions sort its capabilities.

Sections and submenus are **arrangement**: the shape of a list the engine builds
itself, which it says in its own words (`display: 'section'`, `display: 'dropdown'`,
`group`), with no frappe-ui key ever reaching a script. That is why they are in, and
why a script does not spell them in `props`.

Everything else falls under the declared-props line. A menu row's `props` is filtered to
the option's declared keys: `description`, `selected`, `disabled`, `theme`, `condition`
and `route`. A declared key is in. An undeclared one warns and is dropped.

The exclusions the earlier line drew by hand now fall out of the same rule:

- A switch is **state**, which the engine neither holds nor has a verb for, and it is
  not a declared key of an action option here.
- The custom row component is deprecated upstream and is not declared, so it stays out.
  Adopting it would mean inheriting somebody else's exit.
- `route` in `props` is a declared key, but it loses to `run` exactly as `href` does: an
  item with `run` drops `route` from its binding.
- Trigger width, side, alignment and portal target are **host layout**, which no script
  has ever been able to set anywhere else on the page. They are the menu's keys, not the
  option's, so no row's `props` reaches them.

A menu row's `props` and a `Button`'s `props` are different lists. A button the row
demotes into `⋯` is drawn by the menu option, so its `props` is read against the
option's keys there: `disabled` carries over, and a `Button`-only key such as `variant`
warns and is dropped from the demoted copy.

There is no compiler help here. A menu option type carries an index signature, so a key
the option does not declare type-checks and would vanish; that is why the host
hand-lists the declared keys instead of reading them off the type.

### The same line, outbound

The rule above governs what goes _in_ to `page`. The symmetric one governs what comes
back out:

**Every object `page` hands back is read-only.** A script may not mutate `page`'s
return values into shared state; a write throws, names the member, and points at the
supported verb. `page.doc` is the one exception, and it is one by design — mutating the
document is the API. A **row handle** from `page.rows()` inherits that exemption for
the same reason: it addresses a row *inside* `page.doc`, so `row.amount = …` is a
document write spelled shorter. The array holding the handles is read-only as usual.

This is a rule about `page`, not a list of members, and it binds every member added
after it without anyone re-deriving the argument. The reason it has to be a rule is
that almost nothing `page` returns belongs to your record: `page.roles` is the
session's roles array, shared by the entire application; `page.perms` is a view shared
by every source on the page; `page.meta` is a cached document that outlives navigating
to another record — and to another doctype. A script that sorted `page.roles` in place
was corrupting all three for everyone, permanently, with no error and no way to trace
it.

Only writes are refused. **Reads, `find`, `filter`, `map`, `includes` and spreads all
keep working**, and a script that legitimately wants to reorder or edit copies first:

```js
const sorted = [...page.roles].sort();
const visible = page.meta.fields.filter((field) => !field.hidden);
```

Both allocate something new, and what you do to it afterwards is your business.

### The one hand-through: `page.router`

Both rules above have exactly one standing exception. It is written down here because
the engine claimed for a long time that it *was* written down here, and it was not.

`page.router` is `host.router`, handed straight through. The outbound rule does not
wrap it because it is vue-router's object rather than ours, and the inbound rule never
catches it because nothing is being picked apart key by key — the whole dependency is
the member.

The cost is precisely the cost those rules exist to prevent, so it is worth saying
plainly. A script calling `page.router.replace({ query: { … } })` is coupled to two
things it does not own: vue-router's API, and **this host's URL scheme**. A stored
script that names a query parameter goes on naming it after the host renames it, and
nothing warns, because from `page`'s side nothing happened.

It stays because withdrawing a shipped member is a break we have no reason to inflict,
not because it earns its keep. Two rules bound it:

- **No `page` capability may _require_ it.** Where reaching the router is the only way
  to do something, that is a missing verb and the verb gets built. Moving the reader
  between tabs was the case that established this: `activate()` exists on both tab
  surfaces so that the capability is never spelled as a URL edit.
- **It is not a precedent.** No second member is handed through on the strength of this
  one.

## What an app publishes: the `import_map` hook

A stored script imports by bare name, and the document's import map says what those
names are. The framework publishes four bare names, `vue`, `vue-router`, `frappe-ui` and
`@framework/ui`, and one name of its own by the rule below, `frappe/i18n`. An app
publishes its own with one hook:

```python
# apps/crm/crm/hooks.py
import_map = {
	"crm/ui": "@frappe/crm-ui",           # a package the app declares under `dependencies`
	"crm/lib": "./frontend/lib/index.js", # a file, rooted at the app's source dir (apps/crm/crm)
}
```

A stored script then writes `import { DealCard } from "crm/ui"`, and the name resolves
to a chunk of the bench's one bundle.

**A published name is a promise, and the name rule is what makes it keepable.** Every name
an app publishes is `<app>/<alias>`, where `<app>` is the app's Python name; the
framework's four bare names are the one exemption. So two apps cannot publish one name, no
app can shadow a framework name, and the name outlives the package behind it: the app can
move `crm/ui` from one package to another, or from a package to a file, without touching a
single stored script. The name is the app's promise to script authors, not the package's.

What the build checks, before vite starts, naming the app, the key and the value:

- the name starts with `<app>/`, and is not one of the framework's four;
- a package value is declared under `dependencies` in the app's `desk.package.json`;
- a file value resolves inside the app's source dir, and exists.

What the promise does **not** cover, in the same voice as the rest of this document:

- **Only named exports are published.** `export * from` forwards named exports and
  nothing else, so a published file's default export does not reach a script.
- **A published chunk's stylesheets load with the shell**, on every cold load, whether or
  not a script imports the name. The build prints the size per published name so the
  cost is visible; publish a small entry, not a whole app.
- **The build styles what it has source for.** A published **file** is scanned wherever
  it sits in the app, its own folder included, so the classes it writes have rules in
  the desk stylesheet. A published **package** is not scanned: it ships its own compiled
  CSS and imports it, the way `frappe-ui` does. The build line says which:
  `[styles: scanned]` for a file, `[styles: yours]` for a package. The framework's own
  names print `scanned`, because their sources are already in the content list.
  `public/` is never scanned, because compiled output is not a source of class names.
- **What is behind the name moves on the app's cadence**, exactly as the framework's
  four move on theirs. `page` being unchanged does not mean `crm/ui` still exports what
  it did.

## What you commit to when you contribute

A file you contribute or a name you publish is built from the framework's tree. It runs
on the framework's version of the six shared libraries, `vue`, `vue-router`, `frappe-ui`,
`@framework/ui`, `reka-ui` and `dompurify`, and on no other. Declare the ones you import
in your desk declaration file with a range that includes the version the framework ships,
which is the resolved version in `frappe/frontend/yarn.lock.base`, not the floor of its
range. `@framework/ui` has no version; declare it as `"*"`. If your range excludes the
shipped version, the build is refused before vite starts and the message names both sides:

```
frappe-ui: the framework ships 1.0.0-beta.63; gameplan needs >=1.0.0-beta.70
```

You cannot move the framework's pin from your app. A newer release arrives when the
framework takes it. Your app's own frontend, if it has one, is a separate bundle with its
own tree and is not affected.

## What a script says to a reader: `frappe/i18n`

The framework publishes `frappe/i18n` from a file of its own source, by the same
`<app>/<alias>` rule an app follows. A stored script and a contributed or published file
write the same import line, and no declaration is needed for it. It exports two
functions and nothing else:

```js
import { __, __n } from "frappe/i18n"

__("Deal {0} loaded", [page.docname])           // text, replacements?, context?
__n("{0} open task", "{0} open tasks", n, [n])  // singular, plural, count, replacements?, context?
```

`__(text, replacements?, context?)` is desk v1's function with desk v1's shape. It looks
up `text:context` first, then `text`, and returns the text itself when neither has a
translation. `{0}`, `{1}` in the result fill from `replacements` by position; a
placeholder with no value stays as written.

`__n(singular, plural, count, replacements?, context?)` reserves the name for plural
catalogs the framework does not have. Until it does, it picks the English form by
`count === 1`, looks that form up like `__` does, and fills replacements the same way.

What the promise does **not** cover:

- **A published file's strings are extracted; a stored script's are not.** The POT walk
  reads `__("...")` in every `.js`, `.ts` and `.vue` file of an app's source, so a
  published file's strings reach the app's catalog. A stored Client Script is a site's
  own row and is never walked: a site translates its strings through `Translation` rows,
  which merge into the same language set the shell fetches. `__n`'s two forms are not
  extracted either; one `Translation` row per form covers them.
- **The first paint can be English.** Messages are fetched apart from boot and never
  awaited. A template that calls `__` re-renders when they land; a string a script copied
  into a variable in `onLoad` does not.
- **There is no global.** No `window.__`; the import is the only door, for a published
  file and a stored script alike.

## What an app declares: `desk.package.json`

An app's desk v2 code is built from the framework's tree, and that tree holds only what
is declared. The app declares in one file beside its `hooks.py`:

```json
// apps/crm/crm/desk.package.json
{
	"dependencies": {
		"vue": "^3.5.13",
		"@frappe/crm-ui": "^1.2.0"
	}
}
```

- **One key.** The file holds `dependencies` and nothing else. Any other key fails the
  build before vite starts, naming the app, the key and the file.
- **No file, no packages.** An app that declares nothing can import nothing but what its
  contributed files reach through `@shell`.
- **Install follows the declaration, not the import graph.** Everything the file declares
  is installed, whether or not a contributed file imports it. The build prints one line
  per app after install, naming the packages the app added and the size of each
  package's own folder, or `no packages added`. Dependencies yarn hoists beside it are
  not counted. A package nobody imports is the author's own act, and the line names it.
- **The repo root `package.json` is not read.** It serves the app's other bundles, such as
  a standalone SPA or a desk v1 build, on their own pins. Nothing declared there reaches
  the desk v2 tree, and nothing declared here reaches those.
- **A shared library is declared, never moved.** `vue`, `vue-router`, `frappe-ui`,
  `@framework/ui`, `reka-ui` and `dompurify` come from the framework's `package.base.json`
  at the framework's pin. An app declares the one it imports so the resolver admits the
  import; it cannot change the version.

## What an app styles with: `tailwind.preset.js`

The desk builds one stylesheet from one Tailwind config, the framework's. An app adds
theme leaves to it through one file, found where it sits. Every app on the bench is read,
whether or not it contributes a file or publishes a name:

```js
// apps/crm/crm/frontend/tailwind.preset.js
export default {
	theme: {
		extend: {
			colors: { "crm-ink": "#1f2937" },
		},
	},
	plugins: [],
};
```

- **`export default`.** The file loads the same way whether or not the app's repo root
  `package.json` says `"type": "module"`.
- **Two keys.** The file holds `theme` and `plugins` and nothing else. `content`,
  `safelist`, `darkMode`, `prefix`, `corePlugins`, `presets` and every other key fail
  the build, naming the app and the key. Nobody gets a safelist.
- **Under `theme.extend` only.** A plain `theme.colors` replaces the whole scale, the
  framework's included, and is refused. A leaf under `extend` is added.
- **A leaf has one writer, and the framework is one of the parties.** A leaf the
  framework theme already defines, `colors.gray.100` or `spacing.4`, cannot be set by an
  app; the refusal shows the framework's value. Two apps writing one leaf with different
  values are refused, naming each app and its value. Two apps writing one leaf with an
  equal value pass, as do different leaves under one parent.
- **Refused once, before anything is built.** The check runs while the vite config loads,
  so the message prints once, at the top, and no transform runs:

  ```
  The desk shell builds one stylesheet, which admits one value for each theme key. These presets conflict:
    colors.brand: crm wants "#a00000", erpnext wants "#0000b0"

  Change the presets and build again.
  ```

- **Plugin and variant names are not checked.** Plugins concatenate in `sites/apps.txt`
  order. Two plugins registering one variant name give the later app's variant with no
  error.

## Which apps the build reads: `sites/apps.txt`

The build takes its app list from `sites/apps.txt`, `frappe` first and then the file's
order, and never scans `apps/`. `bench get-app`, `bench remove-app` and
`bench setup requirements` rewrite the file from the folders, so after a bench command the
file is current. If you clone or remove an app by hand, run `bench setup requirements`
before `bench build`.

The build prints the list it read on one line, before the per-app cost lines:

```
apps: frappe, crm, erpnext
```

That line is where to look when an app you expect is missing from the bundle. An app
listed in the file whose folder is gone fails the build, naming the app.

Desk v1's build scans `apps/` for its list and falls back to the file only when the scan
throws. Its Python half reads the file. On a bench where the file is stale the two halves
disagree, and the scan is a second source of truth for one fact. Desk v2 keeps the one
source, so a stale file is a bench matter, not something the build repairs or checks.

## Asking what a host has

`page` carries **no version number**, and will not get one. A version number invites
`if (page.version >= 3)` branches inside stored scripts that nobody will ever prune,
and it implies a contract this document has just declined to make.

Ask with plain JavaScript instead:

```js
if (typeof page.dialog.form === "function") {
  // …
}
```

Feature detection is the supported way, and it is the only tool a Client Script has — it
cannot pin a host version the way a file script can.

## When something is removed

A removed verb is **tombstoned for one major version**: the name stays, as a function
that throws a message naming the removal and what replaces it, and is deleted a major
later. So a script that breaks tells you _why_ it broke rather than only that it did.

Names that were removed but never tombstoned are caught by a second net: reading one
off `page` warns in the console, by name. Reading a name that never existed stays
quiet — probing with `typeof` is legitimate and must not be punished.

Where you hear about it:

- **Tombstone hit** — console error, an **Error Log** row through the customization
  error reporter, and a toast shown once per script per session to users who can edit
  Client Scripts. A removal that fires on a live site is an upgrade breaking a
  customer's customization; it is not a developer-console matter, and it is not gated
  to dev builds.
- **Unknown-member warning** — console only, always on. Advisory, and too frequent to
  put in the Error Log.

## Forward compatibility is not a goal

A script written against a newer host, run on an older one, is not supported. A
handler key this host has never heard of warns once and never fires; a verb it does
not have simply is not there. Target the host you run on. A file script is rebuilt
against a host, and a Client Script is authored in an editor connected to the very site
it runs on, so there is no path we are closing off here — only one we are declining to
invent.

## What is not promised, in exactly those words

- **No version, no negotiation.** `page` carries no version number and never will. Ask
  with `typeof`, not with a number.
- **Nothing reachable _through_ `page` is stable.** frappe-ui components you pass to
  `add()` or `open()`, and anything you import from the framework's four names or an
  app's published ones, move on their own cadence. `page` being unchanged does not mean your script still works.
- **New frappe-ui features do not reach your script for free.** Every `page` verb is
  an allowlist.
- **No forward compatibility.** A script using an event this host has never heard of
  warns once and never fires.
- **A removed verb will break your script.** We tombstone it for one major so the
  error names the removal, and we tell you in the Error Log. We do not keep it
  working.
- **You may not write to what `page` hands you.** Every return value is read-only
  except `page.doc`; a write throws and names the verb to use instead. Copy it if you
  need to change it.
- **No migration tooling for stored scripts.** A Client Script is text in a table.
  Nothing rewrites it for you.
- **None of this is a security boundary.** Error isolation is not sandboxing, and
  anything a script hides is hidden from the eye, not from the server.
- **A class typed into a Client Script gets no rule.** The stylesheet is built from
  files on disk, and a script is a row in a table. The palette below is the set a
  script can rely on. The build writes every class it generated to
  `sites/assets/frappe/frontend/classes.json`, and saving a `Client Script` warns with
  every class in it that has no rule. The warning never blocks the save, and it is silent
  on a bench that has not run the build. Nothing generates a class on demand.

## The palette: the classes a stored script can rely on

`frontend/palette.txt` lists these names as plain text, and the build scans it like any
other file, so every one of them has a rule in the desk stylesheet whether or not a desk
component uses it. It is the framework's own file: no app adds to it, and it is not a
Tailwind `safelist`. Steps are 4px each; colour steps follow frappe-ui's scale.

| Group | Classes |
| --- | --- |
| Spacing: padding, margin and gap, in 4px steps | `p-0` `p-1` `p-2` `p-3` `p-4` `p-5` `p-6` `p-8` `px-0` `px-1` `px-2` `px-3` `px-4` `px-5` `px-6` `px-8` `py-0` `py-1` `py-2` `py-3` `py-4` `py-5` `py-6` `py-8` `pt-0` `pt-1` `pt-2` `pt-3` `pt-4` `pt-5` `pt-6` `pt-8` `pb-0` `pb-1` `pb-2` `pb-3` `pb-4` `pb-5` `pb-6` `pb-8` `pl-0` `pl-1` `pl-2` `pl-3` `pl-4` `pl-5` `pl-6` `pl-8` `pr-0` `pr-1` `pr-2` `pr-3` `pr-4` `pr-5` `pr-6` `pr-8` `m-0` `m-1` `m-2` `m-3` `m-4` `m-5` `m-6` `m-8` `mx-0` `mx-1` `mx-2` `mx-3` `mx-4` `mx-5` `mx-6` `mx-8` `my-0` `my-1` `my-2` `my-3` `my-4` `my-5` `my-6` `my-8` `mt-0` `mt-1` `mt-2` `mt-3` `mt-4` `mt-5` `mt-6` `mt-8` `mb-0` `mb-1` `mb-2` `mb-3` `mb-4` `mb-5` `mb-6` `mb-8` `ml-0` `ml-1` `ml-2` `ml-3` `ml-4` `ml-5` `ml-6` `ml-8` `mr-0` `mr-1` `mr-2` `mr-3` `mr-4` `mr-5` `mr-6` `mr-8` `gap-0` `gap-1` `gap-2` `gap-3` `gap-4` `gap-5` `gap-6` `gap-8` |
| Radius | `rounded-0` `rounded-1` `rounded-2` `rounded-3` `rounded-4` `rounded-5` `rounded-6` `rounded-7` `rounded-8` `rounded-9` `rounded-full` `rounded-none` |
| Backgrounds | `bg-surface-gray-1` `bg-surface-gray-2` `bg-surface-gray-3` `bg-surface-gray-4` `bg-surface-gray-5` `bg-surface-blue-1` `bg-surface-blue-2` `bg-surface-blue-3` `bg-surface-blue-4` `bg-surface-blue-5` `bg-surface-green-1` `bg-surface-green-2` `bg-surface-green-3` `bg-surface-green-4` `bg-surface-green-5` `bg-surface-orange-1` `bg-surface-orange-2` `bg-surface-orange-3` `bg-surface-orange-4` `bg-surface-orange-5` `bg-surface-red-1` `bg-surface-red-2` `bg-surface-red-3` `bg-surface-red-4` `bg-surface-red-5` |
| Text colours | `text-ink-gray-4` `text-ink-gray-5` `text-ink-gray-6` `text-ink-gray-7` `text-ink-gray-8` `text-ink-gray-9` `text-ink-blue-4` `text-ink-blue-5` `text-ink-blue-6` `text-ink-blue-7` `text-ink-blue-8` `text-ink-blue-9` `text-ink-green-4` `text-ink-green-5` `text-ink-green-6` `text-ink-green-7` `text-ink-green-8` `text-ink-green-9` `text-ink-orange-4` `text-ink-orange-5` `text-ink-orange-6` `text-ink-orange-7` `text-ink-orange-8` `text-ink-orange-9` `text-ink-red-4` `text-ink-red-5` `text-ink-red-6` `text-ink-red-7` `text-ink-red-8` `text-ink-red-9` |
| Borders | `border` `border-t` `border-b` `border-outline-gray-1` `border-outline-gray-2` `border-outline-gray-3` `border-outline-blue-1` `border-outline-blue-2` `border-outline-blue-3` `border-outline-green-1` `border-outline-green-2` `border-outline-green-3` `border-outline-orange-1` `border-outline-orange-2` `border-outline-orange-3` `border-outline-red-1` `border-outline-red-2` `border-outline-red-3` |
| Text | `text-2xs` `text-xs` `text-sm` `text-base` `text-md` `text-lg` `text-xl` `text-2xl` `text-3xl` `font-medium` `font-semibold` `font-bold` `text-left` `text-center` `text-right` `truncate` `italic` `underline` |
| Layout | `flex` `inline-flex` `flex-col` `flex-row` `flex-wrap` `flex-1` `shrink-0` `grow` `items-start` `items-center` `items-end` `items-stretch` `justify-start` `justify-center` `justify-end` `justify-between` `self-start` `self-center` `self-end` `grid` `grid-cols-1` `grid-cols-2` `grid-cols-3` `grid-cols-4` `col-span-2` `col-span-3` `col-span-4` `block` `inline-block` `hidden` `w-full` `h-full` `min-w-0` `overflow-hidden` `overflow-auto` |
