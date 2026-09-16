# Writing a Client Script for the record page

What `page` offers a script, region by region, with the script each region's design was
judged by as its worked example. [`COMPATIBILITY.md`](./COMPATIBILITY.md) says which of
this survives an upgrade; this document says what there is.

One section per region of the page. A region's section lands with the region, so a
region not listed here is not yet addressable.

## Where a script runs

A record-page script is a `Client Script` row with `view = Record` and `dt` set to the
doctype. Its body is an ES module whose default export is an object of handlers, keyed by
event (`onRefresh`, `beforeSave`, `afterSave`, `onTabChange`, `onFormTabChange`) or by a
fieldname. Every handler receives `page`.

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

**Every place on the page is a list, every list takes a component item, and `before` /
`after` names a neighbour.** There is no vocabulary of places on top of that: no zone or
slot words say where a thing goes, a neighbour does. The frame, the header row and the
panel are each a list that accepts the same item shape, `name`, `component`, `props`, and
speaks the seven verbs and `clear`. A script author learns one item and one position
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
| `body` | The Details form and the panel. `hide('body')` leaves the header and the bands. |

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

Places inside the body, above the tab strip or above the panel, are not the frame's: they
belong to the form and panel lists. A band costs no new server call, cache key or
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
import-free one that returns a string, as `StageBadge` does. An app extension imports a
`.vue` file. The item is the same.

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
| `quick_actions` | `page.quickActions`, as buttons; as icons when the panel is collapsed to a strip. The framework seeds `print`, `copy_link` and `tags` there: `print` with the right, `tags` with write and only while the record has none. The row names its buttons from the left while the width lasts, then shows icons, then folds the rest into a `⋯` menu. A script hides or reorders them by name. |
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

## The field: `page.fields`

The Details form is the main column of the record: the doctype's `Details` layout, or its
fields in DocType order when no row applies. `page.fields` is an **overlay** on the fields
authored there, cleared before every replay. It has no `add`, `move` or `order`, since
ordering is the Form Layout's job; it speaks `hide`, `show`, `update`, `has` and `get`,
and one **act**, `focus(fieldname)`.

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
