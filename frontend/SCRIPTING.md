# Writing a Client Script for the record page

What `page` offers a script, region by region, with the script each region's design was
judged by as its worked example. [`COMPATIBILITY.md`](./COMPATIBILITY.md) says which of
this survives an upgrade; this document says what there is.

One section per region of the page. A region's section lands with the region, so a
region not listed here is not yet addressable.

## Where a script runs

A record-page script is a `Client Script` row with `view = Record` and `dt` set to the
doctype. Its body is an ES module whose default export is an object of handlers, keyed by
event (`onRefresh`, `beforeSave`, `afterSave`, `onTabChange`, `onFormTabChange`, `onPost`)
or by a fieldname. Every handler receives `page`.

`onRefresh` is a **replay**: the surfaces are cleared and rebuilt from the host's
built-ins on every pass, so a conditional customization is a plain `if` over `page.doc`,
with no `else` to undo it. Scripts run in `run_order`, and on one name the last to write
wins.

```js
export default {
  onRefresh(page) {
    if (page.doc.status === 'Won') page.header.hide('save')
  },
}
```

`onTabChange` and `onFormTabChange` receive `page` only and fire on a change between two
shown tabs; the handler reads `page.tabs.active` or `page.form.tabs.active`. A script's
`activate` during the first load opens the page on that tab and fires no `onTabChange`,
because no tab was shown before it.

**Every place on the page is a list, every list takes a component item, and `before` /
`after` names a neighbour.** There is no vocabulary of places on top of that: no zone or
slot words say where a thing goes, a neighbour does. The frame, the header row, the panel
and the form are each a list that accepts the same item shape, `name`, `component`,
`props`, and speaks the seven verbs and `clear`. A script author learns one item and one position
spelling; the sections below only refer to it.

## The frame: `page.frame`

The page's column is **one list**. Its two built-in regions are `header`, the pinned row
of crumbs and Save, and `body`, the Details form and the panel side by side. A script adds
a **band** before, between or after them: a banner under the crumbs, a colour strip along
the top, a footer. The surface speaks the eight verbs, `clear` among them.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. `header` and `body` are taken. |
| `component` | A Vue component that draws the band. It receives `{ ...props, page }`, unfiltered, as a header or panel component does. |
| `props` | Forwarded to the component beside `page`. |
| `gutter` | `false` makes the wrapper bare, so the band runs edge to edge. Omitted, the wrapper takes the page's side padding, and the band's content lines up with the crumbs. |
| any other key | Not read: dropped from the item on `add` and `update`, and a development build warns once, naming the item and the key. |

A band is script only; it has no record form yet.

### The built-ins

| Name | What it is |
| --- | --- |
| `header` | The pinned header row: `page.header`'s list. `hide('header')` draws no row, the same result as `page.header.clear()`. |
| `body` | The body row: `page.body`'s list, the Details form and the panel among its columns. `hide('body')` leaves the header and the bands. |

`move` on a built-in warns in a development build and does nothing; so does an `add`
under a built-in's name, and `order()` leaves a region it names where it is. `hide`, `show` and `update` on a built-in work as on any item,
though `update` has nothing to draw on one. `clear()` hides both regions and every band
present at the call: a blank page. A later `add` draws, and `show('header')` brings the
row back.

### Where a band sits

`{ before: 'header' }` is the top of the page, `{ after: 'header' }` or `{ before: 'body' }`
is between the row and the body, and `{ after: 'body' }` is the bottom. An anchor can also
name another band; an absent anchor appends at the bottom. Two scripts adding at one place
are ordered by run order, then by the position: a later script's `{ after: 'header' }`
lands directly after the header, above the earlier script's band there.

A band before or between the regions is pinned with the header row and does not scroll; a
tall one takes its height from the scroll region. The band after the body sits at the
bottom of the page. The wrapper is a bare block, with no vertical padding, border or
minimum height: the component owns those, and `gutter` is the only word the shell adds for
the look. A band is the way to a full-width strip; a header component with a negative
margin is no longer needed for that.

Places inside the body are not the frame's: a column beside the form is `page.body`'s,
and a place above the tab strip or above the panel belongs to the form and panel lists. A band costs no new server call, cache key or
permission check, since it comes from the scripts already loaded, and one wrapper element
per band on a cold load.

### The script this design was judged by

```js
// A band between the header row and the body, pinned with the header, aligned with the crumbs.
page.frame.add({ name: 'stage_banner', component: StageBanner, props: { tone: 'warning' } }, { after: 'header' })

// A colour strip at the top of the page, edge to edge.
page.frame.add({ name: 'env_strip', component: EnvStrip, gutter: false }, { before: 'header' })

// A footer.
page.frame.add({ name: 'audit_note', component: AuditNote }, { after: 'body' })

// A later script hides a band, or the header row, by name.
page.frame.hide('stage_banner')
page.frame.hide('header')
```

## The body: `page.body`

The row under the header is **one list of columns**. Its two built-ins are `form`, the
Details form, and `panel`, the side panel; the panel is a column that happens to be built
in, with the same keys and the same verbs as one a script adds. A script adds a column
before the form, between the two, or after the panel. All eight verbs work on every item,
built-ins included: `move('panel', { before: 'form' })` puts the panel on the left.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. `form` and `panel` are taken. |
| `component` | A Vue component that draws the column. It receives `{ ...props, page }`, and `collapsed` when the column is collapsible. |
| `props` | Forwarded to the component beside `page`. |
| `width` | Absent, the column **flexes**: it shares what the fixed columns leave with the other flex columns, equally. Present, the column is **fixed** at that many pixels, and the reader can drag it. |
| `minWidth`, `maxWidth` | The drag range of a fixed column; 240 and 640 when omitted. Not read on a flex column. |
| `collapsible` | `true` gives the column the round chevron and a 48px strip. The component draws the strip's content itself from `collapsed`. On a flex column the chevron sits on the left edge with no drag. Default `false`. |
| `gutter` | `false` makes the content bare; omitted, the content takes the page's side padding. The strip never does. |
| any other key | Not read: dropped on `add` and `update`, and a development build warns once, naming the item and the key. |

A column is script only; it has no record form yet.

### The built-ins

| Name | What it is |
| --- | --- |
| `form` | The Details form, a flex column. `hide('form')` is allowed and warns in a development build; the panel keeps reading `page.fields`. |
| `panel` | The side panel: fixed at 380 (drag range 320 to 640), `collapsible`. Its component is the host's. The host still draws no panel when every section is hidden, as it draws no header row when the row is empty; `has('panel')` stays true. |

An `add` under a built-in's name warns and adds nothing. `clear()` hides every column,
built-ins included: an empty body. A later `add` draws, and `show('form')` brings the form
back.

### What the engine draws

Every column scrolls on its own. A 1px separator sits between adjacent visible columns; no
column draws its own border. A fixed column gets a drag edge on the side that faces the
nearest open flex column, and no edge when none is open. Dragging past the range
clamps; a drag within 7px of the script's `width` snaps to it; on a collapsible column a
drag 60px under `minWidth` shuts it.

The reader's width and collapsed state are remembered in the browser, per user and column
name, and **win over the script's `width`**, which is only the default the first time.
The remembered width is clamped to the script's `minWidth` and `maxWidth` on read. There
is no collapse verb: `hide` and `show` are a script's, the strip is the reader's.

### Narrow screens

An open flex column keeps at least 320px. When the row cannot fit that, or fixed columns
alone overflow it, the host drops fixed columns from the outside in until it fits: right
of the panel first, then left of the form, then the panel, then between the two. A flex
column is never dropped. A dropped column is not drawn but stays on the surface, so `has`
and `show` see no change. A dropped collapsible column draws its strip. A script cannot
observe the drop.

### The script this design was judged by

```js
// Client Script, view = Record, doctype = Lead
import Summary from '@myapp/Summary.vue'
import Assistant from '@myapp/Assistant.vue'

export default {
  setup(page) {
    page.body.add({ name: 'summary', component: Summary, width: 280, minWidth: 200 }, { after: 'form' })
    page.body.add({ name: 'assistant', component: Assistant, collapsible: true }, { after: 'panel' })
    page.body.move('panel', { before: 'form' })
    page.body.hide('form') // warns: the Details form is hidden
  },
}
```

On a phone that page draws the panel's strip and the flex assistant: the summary, right of
the panel, is dropped first. On a desktop all three show; the reader drags the summary and
collapses the assistant, and both are remembered.

## The header row: `page.header`

The row is **one flat list** of items, drawn in **two zones**. Every crumb, button, menu
entry and `Save` is an item on it, so every one of them has a name a script can reach.

The surface speaks the eight verbs: `add`, `hide`, `show`, `update`, `move`, `has`,
`order`, `clear`. `add` takes one item or an array, and a `position` of `{ before }` or
`{ after }` naming another item; an anchor that names nothing appends. `clear` hides
every item present at the call, built-in or added by an earlier script; it is an op in
source order like `hide`, so a later `add` draws, a later `show(name)` brings one item
back, and the items stay addressable. The same verb is on `page.panelSections`,
`page.tabs` and `page.quickActions`.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. One namespace for the whole row. |
| `label` | The text drawn. |
| `zone` | `'left'` or `'right'`. Omitted means `'right'`. |
| `display` | On the right: `'button'`, `'dropdown'`, `'section'`, or omitted for an entry in `⋯`. On the left: `'crumb'`, `'dropdown'`, or omitted for a button. |
| `href` | A path inside this app's prefix; a crumb with one is a link. |
| `run` | `(page) => any`. A crumb or button with one runs it; `run` wins over `href`. |
| `group` | The container this sits in. A member sits in its container's zone. A name no item declares forms a band of its own in `⋯`, with no heading. |
| `icon` | `lucide-<name>`, any of the shell's lucide icons; the page draws one the bundle never used from its sprite. |
| `component` | A Vue component that draws the item itself, as a panel section's does. It is a control in its zone and receives `{ ...props, page }`. |
| `props` | Forwarded to whatever draws the item, filtered to what that thing declares. A control in the row (`display: 'button'`, a `display: 'dropdown'` trigger, `Save`) is drawn by frappe-ui's `Button`: `theme`, `size`, `variant`, `iconLeft`, `iconRight`, `tooltip`, `loading`, `loadingText`, `disabled`, `route`, `link`, `type`, plus `class`; not `style`. A row in a menu (an entry in `⋯`, a member of a dropdown, a button demoted into `⋯`) is drawn by the menu option: `description`, `selected`, `disabled`, `theme`, `condition`, `route`. An item's own `component` receives `{ ...props, page }` unfiltered. A key the drawer does not declare is dropped, and a development build warns once, naming the source, the item and the key. `label` and `icon` go on the item, not in `props`. With `run` or `href` on the item, `route` and `link` in `props` are dropped. A script's `props` beat the host's defaults, except `Save`'s `disabled` (the dirty flag) and `loading` (a save in flight). |
| any other key | Not read: dropped from the item on `add` and `update`, and a development build warns once, naming the item and the key. The same holds on `page.quickActions`, `page.tabs` and `page.panelSections`. |

`zone` and `display` are orthogonal: a favourite star is `{ zone: 'left', display: 'button' }`.
A `section` on the left has no menu to title a band in, so its members render in its
place. A `crumb` on the right draws nowhere, so it lands in `⋯`. Both warn in a
development build.

A `component` is a control in either zone. On the left its wrapper is `flex-1 min-w-0`:
a sole component fills the row, and one between the crumbs and a button takes the spare
width, so that button sits at the zone's far end; the crumbs keep their collapse rule.
On the right its wrapper is `shrink-0` and it spends one of the zone's slots; past the
budget it is not drawn, and a development build warns, since a component cannot live in
`⋯`. `display`, `group`, `run` and `href` beside a `component` are ignored, each with a
warning: the component draws itself and owns its clicks.

### The built-ins

The generated page seeds these items, in this order:

| Name | Zone | What it is |
| --- | --- | --- |
| `doctype` | left | The doctype's crumb; links to the list. |
| `record` | left | The record's crumb: its title field, or its name. |
| `favourite` | left | The star, after the crumbs: toggles the reader's favourite, and lists everyone who favourited the record on hover. A favourite is a `Favourite` row, read off `docinfo`; it is not desk v1's like and posts nothing on the timeline. |
| `save` | right | The Save button. Disabled by the host while nothing has changed. Pinned: it spends a slot and is never demoted. |
| `favourite_row` | right | The star's row in `⋯`: *Add to favourites* or *Remove from favourites*, whichever the star would do next. Hiding the star keeps this row, and the other way round. |
| `follow_row` | right | The reader's follow, in the star's band: *Follow* or *Unfollow*, whichever comes next. Seeded only when the doctype tracks changes and the reader's *Document follow* setting is on; the `follow` quick action goes with it. |
| `copy_url` | right | A row in `⋯`: copies the record's address, as the `copy_link` quick action does. |
| `copy_id` | right | A row in `⋯`: copies the record's name. |
| `delete` | right | A row in `⋯`, in a band of its own, only with the delete right. Confirms, deletes, and leaves for the list. |

`Save` is **pinned**: it spends one of the right zone's slots and is never demoted into
`⋯`, whatever a script adds around it. It is still an item. `hide('save')` removes it and
frees its slot, as desk v1's `frm.disable_save()` does, and `update('save', { props })`
restyles it, short of `disabled` and `loading`, which the host keeps. A new item with no
anchor lands **after** `Save`; to sit to its left, anchor it:
`page.header.add(item, { before: 'save' })`.

### Fitting

The host decides how many top-level controls the right zone keeps, and a script cannot
observe it. The generated page keeps three. `Save` is pinned and holds one of them while
it is shown. The script's controls fill the rest in list order, and beyond the budget
they demote into `⋯` from the end, so `order()` and `move()` are the priority knob.
With four script buttons before `Save` the row reads `Right one │ Right two │ ⋯ │ Save`,
and `⋯` holds `Right three` and `Right four`. A `component` on the right is dropped
rather than demoted, with a warning. The left zone has no menu and nothing in it is
demoted.

When the row is empty, because every item is hidden or a script called `clear()` and
added nothing, the page draws no row at all: no padding, no border, no `⋯`. The
sidebar's title still draws on its own side.

### A component's edges

The row's padding, border and minimum height are the shell's, not the item's. They come
from frappe-ui's `PageHeader`, which the frame mounts: a minimum height of 48px, a bottom
border, and side padding of `--page-gutter` (12px, and 20px from `sm`). No item key
reaches them.

A component that wants the row's full width pulls itself to the edges with a negative
margin of the same gutter, and pads itself back if it wants its content aligned with
the crumbs:

```html
<div style="margin-inline: calc(-1 * var(--page-gutter)); padding-inline: var(--page-gutter)">…</div>
```

The style form is the one a stored script can rely on: the build never scans a stored
script, so a utility such as `-mx-[--page-gutter]` exists only if some scanned file
already uses it. The height is a minimum: a taller component grows the row. A strip that
wants the page's width is a band with `gutter: false` on `page.frame`, not a header
component with a margin.

### The script this design was judged by

The first act of the map's proof walk: rename the record crumb on a real record.

```js
export default {
  onRefresh(page) {
    page.header.update('record', { label: `${page.doc.name} (reviewed)` })
  },
}
```

And a fuller one, touching both zones:

```js
export default {
  onRefresh(page) {
    // A crumb before the record's, linking to the deals of the same organization.
    // Resolve paths through the router: a hand-built one is wrong under a modular prefix.
    const { name, params } = page.router.currentRoute.value
    page.header.add(
      {
        name: 'organization',
        label: page.doc.organization,
        zone: 'left',
        display: 'crumb',
        href: page.router.resolve({
          name: 'list',
          params,
          query: { organization: page.doc.organization },
        }).path,
      },
      { before: 'record' },
    )

    // A button to the left of Save, and an entry in ⋯
    page.header.add(
      { name: 'snapshot', label: 'Snapshot', display: 'button', run: (p) => p.toast.success('Saved a snapshot') },
      { before: 'save' },
    )
    page.header.add({ name: 'copy_ref', label: 'Copy reference', run: (p) => p.toast.success(p.docname) })

    if (page.doc.status === 'Won') page.header.hide('save')
  },
}
```

And the items the row's ownership was settled on: a button with `props`, a component in
each zone, and no row at all.

```js
page.header.add({
  name: 'approve',
  label: 'Approve',
  icon: 'lucide-check',
  display: 'button',
  props: { variant: 'solid', tooltip: 'Marks the record approved' },
  run: (page) => page.call('myapp.api.approve', { name: page.docname }),
})

// A component in each zone. Each receives { ...item.props, page }.
const StageBadge = {
  props: { page: Object, size: String },
  setup: (props) => () => `Stage: ${props.page.doc.status}`,
}
page.header.add({ name: 'stage_badge', zone: 'left', component: StageBadge, props: { size: 'sm' } }, { after: 'record' })
page.header.add({ name: 'owner_avatar', component: OwnerAvatar }, { before: 'save' })

// Or, in a script of its own: no row at all.
page.header.clear()
```

A stored script has an import map for `vue`, `vue-router`, `frappe-ui` and
`@framework/ui`, so it may `import { h } from 'vue'` for a render function, or write an
import-free one that returns a string, as `StageBadge` does. An app adds names of its
own, `<app>/<alias>`, with the `import_map` hook; see
[`COMPATIBILITY.md`](./COMPATIBILITY.md#what-an-app-publishes-the-import_map-hook). An
app extension imports a `.vue` file. The item is the same.

## The panel: `page.panelSections`

The panel is the column on the right of the record, and it is **one list**. The identity
block, the quick actions, the people rows and the sections of the doctype's Side Panel
layout are all items on it, so a script hides, moves or adds between any of them by name.
Nothing above or beside the list is chrome the engine cannot name.

The surface speaks the eight verbs, `clear` among them, and two **acts**: `open(name)`
and `close(name)`. With every section hidden the page draws no panel, and the form takes
the width.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. One namespace for the whole panel. |
| `label` | Gives the item a header and a chevron. Without one it is a bare block, as the built-ins are. |
| `component` | Rendered for any name the layout does not carry, with `props` and a `page` prop. |
| `props` | Bound onto `component`. |
| `opened` | Whether a section with a header starts open. Meaningless without a `label`, and a dev warning there. |
| any other key | Not read: dropped from the item on `add` and `update`, and a development build warns once, naming the item and the key. |

A name the Side Panel layout carries renders that section's fields, one column, click to
edit. Any other name renders its `component`. The header rule is derived, not declared: a
`label` gives a header; `update('people', { label: 'People' })` gives a built-in one.

### The built-ins

The generated page seeds three items, in this order, and then the layout's sections after
them under the names the Form Layout stores:

| Name | What it is |
| --- | --- |
| `identity` | The title, subtitle, image and tags. The image tile draws when the doctype names an `image_field`; with write, a click uploads into that field, and the header's Save carries it like any edit. A field fetched from a linked record links there instead. |
| `quick_actions` | `page.quickActions`, as buttons; as icons when the panel is collapsed to a strip. The framework seeds `print`, `copy_link`, `follow` and `tags` there: `print` with the right, `follow` under the same gate as `follow_row`, `tags` with write and only while the record has none. The row names its buttons from the left while the width lasts, then shows icons, then folds the rest into a `⋯` menu. A script hides or reorders them by name. |
| `people` | Who the record is assigned to, and who it is shared with. |

A doctype with no Side Panel row shows the three built-ins and nothing else. The panel never
falls back to the Details layout, so no field shows twice; a doctype that wants fields in
its panel ships a Side Panel row.

### The people

`people` edits with the rights the record's `docinfo.permissions` carries: assign and tag
with `write`, share with `share`. Without the right the row reads, and still names the
people. Each pick is one server call, and the row re-reads the sidecar after it; nothing is
painted from the answer, so the row never disagrees with the server.

| Act | Endpoint |
| --- | --- |
| Assign, unassign | `frappe.desk.form.assign_to.add`, `remove` |
| Share, unshare | `frappe.share.add`, `set_permission` with `read` set to `0` |
| Tag, untag | `frappe.desk.doctype.tag.tag.add_tag`, `remove_tag`; searched with `get_tags` |

The share editor is a dialog on the page's own stack, opened through `page.dialog.open`.
The tags stay on `identity`: hiding `people` leaves them standing. The first tag comes from
the `tags` quick action, which goes once the record has one; from then on the chips carry
their own "+".

The surface gains no verb for any of this. A script assigns the way the row does, through
`page.call`, and reloads so the row reads the new sidecar:

```js
export default {
  onRefresh(page) {
    page.quickActions.add({
      name: 'assign_owner',
      label: 'Assign to owner',
      icon: 'lucide-user-check',
      run: async (p) => {
        await p.call('frappe.desk.form.assign_to.add', {
          doctype: p.doctype,
          name: p.docname,
          assign_to: [p.doc.owner],
        })
        await p.reload()
      },
    })
  },
}
```

### Opening and shutting

`open(name)` and `close(name)` are in-page acts on a section that has a header, on
`activate`'s terms: resolved at the call, delivered when the replay commits, and a miss
warns in a development build and does nothing. A hidden section is a miss, since `show()`
is the verb that reveals one. A script's act is the page's, not the reader's: the reader's
own clicks are remembered per doctype in their browser, and a click outranks the act until the
next replay re-issues it.

`page.fields` speaks fieldnames only. Handed a section name, it warns and names the verb
that owns it: `page.panelSections.hide(name)`.

### The script this design was judged by

The second act of the map's proof walk: hide one section by name, and its neighbour stands.

```js
export default {
  onRefresh(page) {
    page.panelSections.hide('people') // "Assigned to" and "Shared with" go
    // 'identity' is still there, and so is 'organization_section'
    console.log(page.panelSections.has('identity'))
  },
}
```

And a fuller one:

```js
const Note = {
  props: { page: Object, text: String },
  setup: (props) => () => `${props.text}: ${props.page.doc.status}`,
}

export default {
  onRefresh(page) {
    // A section of its own, before the people rows; a label gives it a header.
    page.panelSections.add(
      { name: 'note', label: 'Note', component: Note, props: { text: 'Status' } },
      { before: 'people' },
    )
    // The layout's section, moved up and opened for a won deal.
    page.panelSections.move('organization_section', { after: 'identity' })
    if (page.doc.status === 'Won') page.panelSections.open('organization_section')
  },
}
```

## The form: `page.form`

The Details form is the main column of the record, and it is **one list**. Its items are
the sections of the doctype's `Details` layout, in layout order, and the **parts** a
script adds between and inside them: a chart between two sections, a score beside its
field, a note at the top. The surface speaks the eight verbs, `clear` among them, and
every verb works on a section as on a part. Its strip of tabs is `page.form.tabs`, below.

The fields themselves are not items here. A verb on `page.form` that names a data field
records nothing and warns in a development build, naming the verb that owns it:
`page.form.hide("credit_limit") — a field, not a section; page.fields.hide("credit_limit")
is the verb.` A Section, Column or Tab Break is not a field for this rule.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. One namespace with the fields: a field first, then a section, so the Form Layout refuses a section or tab name equal to a fieldname of the doctype. |
| `label` | Draws the part framed like its neighbour: a field label above it beside a field, a section heading above it beside a section. Without one the component is drawn bare. |
| `component` | A Vue component that draws the part. It receives `{ ...props, page }`, as a panel section's does. |
| `props` | Forwarded to the component beside `page`. |
| any other key | Not read: dropped from the item on `add` and `update`, and a development build warns once, naming the item and the key. |

A part is script only; it has no record form. A Form Layout row's column stays a list of
fieldnames, and a part joins the header's component and the frame's band on the map of
what the row does not yet carry.

### The built-ins

The layout's sections, under the names the Form Layout stores: a stored row is named at
save, and a doctype with no `Details` row falls back to its meta, where a section is named
after its Section Break's fieldname, or `section_1` when fields come before the first
break. A section answers `hide`, `show`, `update` with a `label`, `move` and `order` like
any item, and `move` past a section in another tab moves it into that tab. `clear()`
hides every section and part present at the call, and the form draws no section; a later
`add` or `show` draws.

### Where a part sits

The neighbour decides the grain. `{ after: 'credit_limit' }`, a field, draws the part as
a **cell in that field's column**, taking the column's equal share of the width; columns
have no stored width, so there is no width word. `{ after: 'pricing' }`, a section, draws
it as a **full-width block** between the two sections. An absent position appends at the
end of the form, in its last tab. There is no word for a tab: a part before a tab's first
section or after its last one is in that tab. For a cell the neighbour is the position:
`order` ranks the parts that share one neighbour, and a cell leaves its field only by
`move`.

Two scripts adding at one place are ordered by run order, then by the position, as on the
frame. A part costs no new server call, cache key or permission check: it comes from the
scripts already loaded, and folds over the layout the page already fetches, one wrapper
element per part on a cold load.

### The strip: `page.form.tabs`

The tabs inside the form are an **overlay** on the Form Layout's tabs, on `page.fields`'
terms: no `add`, `move` or `order`, since a tab there is a container of fields the
administrator arranged. It speaks `hide`, `show`, `update` with a `label` and nothing
else, `has`, `get`, and `clear()`, which hides every tab present at the call. A script
beats `depends_on` in both directions: `hide()` closes a tab the condition opened,
`show()` opens one it closed.

Two members are the strip's own, since a strip has a reader standing on it. `active` reads
the tab the reader is on as an **identity**, or `''` when the reader is not in the form;
an identity is safe to store, because a Form Layout is named when it is saved and a
relabelled tab keeps its address. `activate(name)` moves the reader, on the record strip's
terms: resolved at the call, delivered when the replay commits, and a hidden, unknown or
other-strip name warns in a development build and moves nobody. Unlike `page.tabs`,
`active` reads the old tab until the form has drawn the move. The handler for a change
on this strip is `onFormTabChange`. The record's own strip, activity to details, is
`page.tabs` and is not this one.

### The script this design was judged by

```js
// A full-width chart between two sections of the Details form.
page.form.add({ name: 'pipeline_chart', label: 'Pipeline', component: PipelineChart, props: { limit: 12 } }, { after: 'pricing' })

// A score beside its field, drawn like a field: label above, the column's width.
page.form.add({ name: 'credit_score', label: 'Credit score', component: Score }, { after: 'credit_limit' })

// A bare banner at the top of the form.
page.form.add({ name: 'stale_note', component: StaleNote }, { before: 'overview' })

// A section is an item: hide it, rename it, move it.
page.form.hide('terms')
page.form.update('pricing', { label: 'Commercials' })
page.form.move('pricing', { before: 'overview' })

// The strip inside the form.
page.form.tabs.hide('products_tab')
page.form.tabs.activate('details')

// The field overlay is unchanged and still reaches the panel.
page.fields.update('probability', { label: 'Win chance (%)' })
```

## The field: `page.fields`

The Details form is the main column of the record: the doctype's `Details` layout, or its
fields in DocType order when no row applies. `page.fields` is an **overlay** on the fields
authored there, cleared before every replay. It has no `add`, `move` or `order`, since
ordering is the Form Layout's job; it speaks `hide`, `show`, `update`, `has` and `get`,
and one **act**, `focus(fieldname)`. The overlay reaches the panel too: one field patch
feeds the Details form and the Side Panel layout, so `page.fields.hide('x')` hides `x` in
both. A part beside a field is `page.form`'s to add, above.

### What `update` takes

| Key | What it does |
| --- | --- |
| `label`, `placeholder`, `description` | The text drawn. |
| `hidden`, `read_only`, `reqd` | Booleans, or `0`/`1` as a DocField spells them. Win over `depends_on`; never lift a permission floor. |
| `options` | A Link target, or a Select's newline-separated choices. |
| `link_filters` | Search filters for a Link field. |
| `precision` | Decimal places for a numeric field. |
| `component`, `props` | Another control in the field's slot, and what to bind onto it. |

A key not named here is dropped with a development warning. `get(fieldname)` answers the
field as it resolves now, post-override and post-`depends_on`, and is read-only.

### The act: `focus(fieldname)`

`focus` switches the form to the field's tab, scrolls to it and puts the cursor in its
control. A read-only field gets the tab and the scroll and no cursor. An unknown or a
hidden field warns in a development build and moves nobody, since `show()` is the verb
that reveals one. On `activate`'s terms: resolved at the call, and inside a replay
delivered when the replay commits. The panel's own expand of a long row uses it.

### Saving: `page.save()`

`page.save()` is the one path; the Save button, `Ctrl+S` / `Cmd+S` and a script all call
it. The order is fixed:

1. The edit still pending in a focused control is flushed, so its field handler runs.
2. `beforeSave` fires. A throw is a veto: nothing is sent, and the message shows.
3. The whole document goes to the server.
4. `afterSave` fires only when the server accepted.

On a clean document it resolves at once, sends nothing and shows nothing. The Save button
is disabled then, with the tooltip "No changes to save", and the shortcut shows that text
as a toast. A record saved by someone else since it was opened opens a dialog naming them
and the fields changed here, with "Reload and lose my changes" and "Keep editing"; nothing
is re-applied silently, and Save fails the same way until a reload.

A field handler runs when the reader commits that field: `status(page)` on a status
change, before any save. A child table's fields are addressed by the table, `products.qty`.

### The script this design was judged by

The third act of the map's proof walk, on a CRM Deal whose `probability` is a Percent field.

```js
export default {
  onRefresh(page) {
    // Rename one field by name; its control keeps working.
    page.fields.update('probability', { label: 'Win chance (%)' })
  },

  // A field handler: runs when the reader commits `status`, before any save.
  status(page) {
    if (page.doc.status === 'Won') page.doc.probability = 100
  },

  // The save channel: a throw here is a veto, and the record stays unsaved.
  beforeSave(page) {
    if (page.doc.probability > 100) throw new Error('Win chance is a percentage')
  },
}
```

The walk: the label reads "Win chance (%)". Set status to Won, and the probability control
shows 100 with no other click. Press Save, and a reload shows 100. Set probability to 120
and press Save: the error shows and the server still has 100.

And the act, with its two misses:

```js
export default {
  onRefresh(page) {
    if (page.doc.status === 'Lost') page.fields.focus('lost_notes')
    page.header.add({
      name: 'focus_sla',
      label: 'Focus SLA status',
      display: 'button',
      run: (p) => p.fields.focus('sla_status'), // read-only: tab and scroll, no cursor
    })
  },
}
```

## The record tabs: `page.tabs`

The strip above the record's body: Activity, Emails, Files, Details and a script's own tabs.
It speaks the eight verbs, `active` and `activate(name)`.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. |
| `label` | The text on the strip. |
| `icon` | `lucide-<name>`, drawn before the label. |
| `component` | Draws the tab's body. It receives `{ ...props, page }`. |
| `props` | Bound onto `component`. |
| `create` | `{ label, icon, run }`: an entry in the composer's `+` menu while the tab is on the strip. |
| `composer` | `true` draws the composer band at the foot of the tab, as on Activity and Emails. |

The page draws a tab's body inside a scroller. A component that draws its own scroller sets
`defineOptions({ scrollsItself: true })`, or `scrollsItself: true` on the component object,
and the tab body adds none.

## The feed: `page.activity`

The Activity tab is **one list, ordered by time**. The server's rows and a script's own
rows sit in it together, oldest first, and a script's row takes its place by its
`timestamp`. Since time orders the list there are no position words: `move` and `order`
warn and do nothing, and `add` takes no `before` or `after`.

The surface speaks `add`, `remove` and `has`, reads its rows through `items`, and has three
acts: `scrollTo(key)`, `reload()` and `types(list)`.

### An item

A script's row:

| Key | What it does |
| --- | --- |
| `name` | The address. It must not be a server row's key; that `add` warns and drops the row. |
| `timestamp` | Where the row sits, written as the server writes one: `2026-09-23 10:15:00`, in the site's time zone. Required, and `update` cannot clear it. `add` and `update` rewrite an ISO `2026-09-23T10:15:00` that way, and move a time with a `Z` or an offset to the site's time zone, so `new Date().toISOString()` lands where it should. Without the site's time zone such a row is dropped, with a warning that prints in production too. |
| `component` | Draws the row, with `props` and a `page` prop. Required. |
| `props` | Bound onto `component`. |
| any other key | Not read: dropped on `add`, and a development build warns once. |

A server row, as `items` hands it back:

| Key | What it holds |
| --- | --- |
| `name` | The row's key: `comment:<name>`, `email:<name>`, `version:<version>-<index>`, `attachment:<name>`, `log:<name>`, and so on. The same key a link or `scrollTo` uses. |
| `type` | `comment`, `email`, `version`, `attachment_log` or `log`. |
| `timestamp` | When it happened. |
| `author` | `{ email, fullname, image }`. |
| `data` | The row's own content, by type. |
| `pending` | `true` on a row posted from this page that the server has not answered yet. |

`items` is read-only; a write throws and names `add` as the verb to use. `has(name)`
answers `true` for a loaded server row and for a script's row. `remove(name)` takes out a
script's row; a server row stays, with a development warning.

### The built-ins

The built-ins are the rows the tab has loaded, not the whole history. The tab reads the
newest 50 rows first and loads older pages as the reader scrolls up, so `items` grows as
the reader goes. A comment, email or attachment another session adds arrives on its own,
and a field change refreshes the newest page.

The first `onRefresh` sees the newest page when the address opens the Activity tab; when it
opens another tab, Emails included, the rows are read as Activity first shows, so that
`onRefresh` sees none. When the address opens the Activity tab, the page's
first paint and first `onRefresh` wait for the newest activity page, a read that starts
with the record read.

A script's rows are rebuilt on every replay, like any surface's, and survive `reload()`,
which reads the server's rows again and leaves the script's alone.

The Emails tab shows the same rows narrowed to emails. It has no surface of its own.

### The acts

`scrollTo(key)` opens the Activity tab, scrolls to the row and highlights it for two
seconds. A row older than the loaded ones is found by loading older pages until it
appears. A field change folded into a run of changes scrolls to the run. If the list ends
without the row, or a script's body replaced the tab's feed, a development build warns
naming the key, and the reader stays where they are. On `activate`'s terms: called in a replay, it is delivered
when the replay commits, and only the last call in a replay counts.

`types(list)` sets the types the Activity tab shows, in `ActivityTimeline`'s spelling:
`['comment', 'email']`, or `{ version: ['status'] }` for changes to named fields only. It
is set by the replay like any op, so a replay that does not call it shows every type
again.

`reload()` reads the server's rows again and resolves when they are in.

A link can point at a row: `…/deal/CRM-DEAL-0001?activity=comment:abc123` opens the
Activity tab, scrolls to that comment and highlights it, as `scrollTo` does.

### The script this design was judged by

```js
export default {
  onRefresh(page) {
    // scroll to a named activity; pages older rows until it is found
    const last = page.activity.items.filter((a) => a.type === 'comment').at(-1)
    if (last) page.activity.scrollTo(last.name)     // 'comment:abc123'

    // a script's own row, ordered by its timestamp among the server rows
    page.activity.add({
      name: 'call:17',
      timestamp: '2026-09-23 10:15:00',
      component: CallRow,
      props: { id: 17 },
    })

    console.log(page.files.items.map((f) => f.name))
  },
}
```

## The files: `page.files`

The Files tab is a smaller list of the same kind: the record's attachments, oldest first,
and a script's own rows placed among them by `timestamp`. It speaks `add`, `remove` and
`has`, reads through `items`, and has one act, `reload()`. There is no `scrollTo` and no
`types`.

### An item

A script's row takes the same keys as a row of `page.activity`: `name`, `timestamp`,
`component` and `props`.

An attachment, as `items` hands it back:

| Key | What it holds |
| --- | --- |
| `name` | The File's name. |
| `file_name`, `file_url` | What the reader sees, and where it downloads from. |
| `file_type`, `file_size` | The extension and the size in bytes. |
| `is_private` | `1` for a private file. |
| `attached_to_field` | The field the file was uploaded into, or empty for a plain attachment. |
| `creation`, `owner` | When and by whom it was attached; `creation` orders the list. |

`items` is read-only. `remove(name)` takes out a script's row, never an attachment: the
tab's own upload button and remove control are drawn only with write.

### The built-ins

The attachments are the record read's `attachments` part. The tab's upload button and a
remove control replace that part from the server's answer, and an upload from another
session arrives on its own. `reload()` reads the part again; a script's rows stay.

### The script this design was judged by

```js
export default {
  onRefresh(page) {
    console.log(page.files.items.map((f) => f.name))
  },
}
```

## The composer: `page.composer`

The band at the foot of the Activity and Emails tabs, and of a script's tab whose item says
`composer: true`. It is not drawn on Files or Details. Collapsed it is a pill; open, it
shows one **writer** in a card. The card is **docked** in the band, or **floating** over the
page; a floating card stays open as the reader moves to another page, and names its record
in its title. `page.composer` is the list of writers, and speaks the eight verbs and four
acts: `open(name, { draft, window })`, `close()`, `active` and `window`.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address `open` takes. |
| `label` | The writer's name in the band. |
| `icon` | `lucide-<name>`. |
| `component` | Draws the writer's body. It receives `{ ...props, page, close }`. |
| `props` | Bound onto `component`. |

A script's writer owns its post: it calls the server, adds its own row with
`page.activity.add`, and calls `close()`.

### The built-ins

`comment`, which posts a comment with its attachments. The row shows in the feed at once and
takes its server key when the server answers; on an error the row goes and the writer
reopens with the draft.

### The acts

`open(name, { draft, window })` opens a writer. If the reader is not on a tab that draws the
band, it moves them to Activity first, or to the first such tab when Activity is hidden. An
unknown or hidden writer, or a strip with no such tab, warns in a development build and
opens nothing. `draft` seeds the writer's draft; a draft already in memory for this record
wins. `window`, `'docked'` or `'floating'`, places the card for this open only; left out,
the card opens where the reader last put it. On `activate`'s terms: called in a replay, it
is delivered when the replay commits, with its `window`.

One card is open at a time. Opening a writer on another record takes the card; the first
record's draft stays in memory.

`close()` collapses the band; the draft stays in memory for the session. `active` is the
open writer's name, or `''`.

`window` reads `'docked'` or `'floating'`: where this record's card is while its writer is
open, and otherwise where the next open will put it. Setting it moves this record's open
card for now; the reader's own choice, which only the card's dock and float button keeps,
stays as it was. With no writer of this record open, or any other value, it warns in a
development build and changes nothing.

`onPost(page, { name })` fires after the server answers a `comment` post, with the new
row's key, `comment:<name>`. It does not fire for a script's writer, which knows when it
posted, nor when the answer comes while the record's page is not open, as for a floating
card sent from another page.

### The script this design was judged by

```js
export default {
  onRefresh(page) {
    page.composer.add({ name: 'call', label: 'Log a call', icon: 'lucide-phone', component: CallWriter })
    if (page.doc.status === 'Lost') page.composer.open('comment', { draft: { content: 'Why lost: ' } })
  },
  onPost(page, { name }) {
    page.activity.scrollTo(name)
  },
}
```
