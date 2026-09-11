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

## The header row: `page.header`

The row is **one flat list** of items, drawn in **two zones**. Every crumb, button, menu
entry and `Save` is an item on it, so every one of them has a name a script can reach.

The surface speaks the seven verbs: `add`, `hide`, `show`, `update`, `move`, `has`,
`order`. `add` takes one item or an array, and a `position` of `{ before }` or
`{ after }` naming another item; an anchor that names nothing appends.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. One namespace for the whole row. |
| `label` | The text drawn. |
| `zone` | `'left'` or `'right'`. Omitted means `'right'`. |
| `display` | On the right: `'button'`, `'dropdown'`, `'section'`, or omitted for an entry in `⋯`. On the left: `'crumb'`, `'dropdown'`, or omitted for a button. |
| `href` | A path inside this app's prefix; a crumb with one is a link. |
| `run` | `(page) => any`. A crumb or button with one runs it; `run` wins over `href`. |
| `group` | The container this sits in. A member sits in its container's zone. |
| `icon` | A lucide name. |

`zone` and `display` are orthogonal: a favourite star is `{ zone: 'left', display: 'button' }`.
A `section` on the left has no menu to title a band in, so its members render in its
place. A `crumb` on the right draws nowhere, so it lands in `⋯`. Both warn in a
development build.

### The built-ins

The generated page seeds three items, in this order:

| Name | Zone | What it is |
| --- | --- | --- |
| `doctype` | left | The doctype's crumb; links to the list. |
| `record` | left | The record's crumb: its title field, or its name. |
| `save` | right | The Save button. Disabled by the host while nothing has changed. |

`Save` is an ordinary item. `hide('save')` removes it, as desk v1's `frm.disable_save()`
does. A new item with no anchor lands **after** `Save`; to sit to its left, anchor it:
`page.header.add(item, { before: 'save' })`.

### Fitting

The host decides how many top-level controls the right zone keeps, and a script cannot
observe it. The generated page keeps three. Beyond that, the last control in list order
demotes into `⋯` first, so `order()` and `move()` are the priority knob. The left zone
has no menu and nothing in it is demoted.

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

## The panel: `page.panelSections`

The panel is the column on the right of the record, and it is **one list**. The identity
block, the quick actions, the people rows and the sections of the doctype's Side Panel
layout are all items on it, so a script hides, moves or adds between any of them by name.
Nothing above or beside the list is chrome the engine cannot name.

The surface speaks the seven verbs, and two **acts**: `open(name)` and `close(name)`.

### An item

| Key | What it does |
| --- | --- |
| `name` | The address every verb uses. One namespace for the whole panel. |
| `label` | Gives the item a header and a chevron. Without one it is a bare block, as the built-ins are. |
| `component` | Rendered for any name the layout does not carry, with `props` and a `page` prop. |
| `props` | Bound onto `component`. |
| `opened` | Whether a section with a header starts open. Meaningless without a `label`, and a dev warning there. |

A name the Side Panel layout carries renders that section's fields, one column, click to
edit. Any other name renders its `component`. The header rule is derived, not declared: a
`label` gives a header; `update('people', { label: 'People' })` gives a built-in one.

### The built-ins

The generated page seeds three items, in this order, and then the layout's sections after
them under the names the Form Layout stores:

| Name | What it is |
| --- | --- |
| `identity` | The title, subtitle, image and tags. |
| `quick_actions` | `page.quickActions`, as buttons; as icons when the panel is collapsed to a strip. |
| `people` | Who the record is assigned to, and who it is shared with. |

A doctype with no Side Panel row shows the three built-ins and nothing else. The panel never
falls back to the Details layout, so no field shows twice; a doctype that wants fields in
its panel ships a Side Panel row.

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
