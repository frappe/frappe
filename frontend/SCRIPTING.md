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

The generated page seeds these items, in this order:

| Name | Zone | What it is |
| --- | --- | --- |
| `doctype` | left | The doctype's crumb; links to the list. |
| `record` | left | The record's crumb: its title field, or its name. |
| `favourite` | left | The star, after the crumbs: toggles the reader's favourite, and lists everyone who favourited the record on hover. A favourite is a `Favourite` row, read off `docinfo`; it is not desk v1's like and posts nothing on the timeline. |
| `save` | right | The Save button. Disabled by the host while nothing has changed. |
| `delete` | right | A row in `⋯`, only with the delete right. Confirms, deletes, and leaves for the list. |

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
