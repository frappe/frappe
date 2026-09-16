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

- **Four surfaces** — `quickActions`, `header`, `tabs`, `panelSections` — each
  speaking the same **seven verbs**: `add`, `hide`, `show`, `update`, `move`, `has`,
  `order`.
- **Two more, `fields` and `formTabs`**, speaking a strict subset of them — `hide`,
  `show`, `update`, `has`, `get`. The subset is the point: the other four arrange items
  a script may also create, while these are authored elsewhere and a script only
  overrides their properties, so there is no `add`, `move` or `order` to mean anything.
  For `fields` the author is the DocType; for `formTabs` — the **Form Layout tabs**, the
  strip inside the record's details tab — it is the administrator editing the layout, and
  a tab there is a container of *fields*, so an `add` would have to invent fields. That is
  `page.dialog`'s job. On both surfaces a script **beats `depends_on` in both directions**:
  `hide()` closes a tab the condition opened, `show()` opens one it closed. On `formTabs`,
  `update` takes a **`label` and nothing else**: rewriting the administrator's `depends_on`
  expression is not a script's to do, and a script wanting conditional visibility already
  has a real `if` in `onRefresh`. `formTabs` additionally carries two members `fields` has
  no use for — `active` and `activate` — for the plain reason that a strip has a reader
  standing on it and a field list does not. What the subset excludes is **arrangement**,
  not reading or navigation.
- **Two tab surfaces, and they are not interchangeable.** `page.tabs` means the **record**
  strip — activity, emails, files, details — and always will; `page.formTabs` means the
  Form Layout strip *inside* details. `page.tabs.active` returns a tab's **name**, because
  those tabs are named by whoever wrote them; `page.formTabs.active` returns an
  **identity** — a resolved address — or `''` when the reader is not in the form. The
  asymmetry is real; do not assume one from the other. An identity is **safe to store in a
  script**: a Form Layout is named when it is *saved*, once and for good, so renaming a
  tab's label or dragging an unlabelled one leaves its address alone. It reads as an
  identity rather than a name because `FormLayout` resolves it itself — it renders in
  dialogs too, where nothing has named the tabs — not because an administrator's tab might
  be nameless. It no longer can be.
- **`activate(name)` moves the reader; it and the panel's `open`/`close` are the only verbs
  that act rather than arrange.** Both tab surfaces carry `activate`, each addressing its
  own strip and no other — `page.tabs.activate('emails')`,
  `page.formTabs.activate('shipping')`. It is a **verb and not a writable `active`** on
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
  about. A **hit is not synchronous**: the move goes through the host's own navigation,
  so `active` on the next line still reads the tab you left — read it in the next
  handler. And a move **fires the strip's change event**, since `onTabChange` and
  `onFormTabChange` fire on any cause; `activate` is the first verb that lets a handler
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
  has already reported it. A script that wants the tab on load reads `page.formTabs.active`
  in `onRefresh` — which is what "state lives on `page`" is for.
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
  `add()` or `open()`, and anything you import from the four shared deps, move on
  their own cadence. `page` being unchanged does not mean your script still works.
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
