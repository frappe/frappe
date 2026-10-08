# ConditionBuilder

A nested tree of conditions joined by AND / OR. The control behind an
Assignment Rule's conditions, an SLA's, or any rule that needs `A and (B or C)`.
Grouping, the group's conjunction and add/remove belong to the component; the row is
a slot, so it fits doctype field conditions and domain-specific rules alike.

`Filter` is the flat, AND-only version of the same idea. Both read their
operator tables and value controls from the same modules, so they cannot drift.
`ConditionOperator` is `Filter`'s operator union minus `timespan`, and `ConditionField`
is `FilterField`, both derived rather than copied, so there is nothing to keep in step.
See [ADR-0008](../../../docs/adr/0008-conditionbuilder-composes-filter-rules.md).

```ts
import { ConditionBuilder } from "@framework/ui/ConditionBuilder";
import type { ConditionField, ConditionGroup } from "@framework/ui/ConditionBuilder";
```

An app that aliases the package to its source directory rather than resolving
`exports` imports `@framework/ui/components/ConditionBuilder`.

## Fields

Either give it a `doctype` and let it derive fields from Meta, as `Filter` does:

```vue
<ConditionBuilder v-model="conditions" doctype="ToDo" />
```

…or supply them yourself, in the `ConditionField` shape (`options` is Frappe's
newline-joined string):

```vue
<ConditionBuilder v-model="conditions" :fields="fields" />
```

`doctype` is read once at setup, so a host that switches doctype should remount
with `:key`. When the Meta request fails the component says so and offers a
retry, rather than presenting every row as though its field had been deleted.

## The model

```ts
{
  // one operator for the whole group: every child joins the next by this
  conjunction: "and",
  conditions: [
    { fieldname: "status", operator: "equals", value: "Open" },
    { fieldname: "subject", operator: "like", value: "refund" },
    {
      conjunction: "or",
      conditions: [
        { fieldname: "priority", operator: "equals", value: "High" },
        { fieldname: "priority", operator: "equals", value: "Urgent" },
      ],
    },
  ],
}
```

A group is anything with a `conditions` array; everything else is a leaf. The
distinction is structural on purpose, so the tree survives a JSON round-trip
with no discriminator to keep in sync. A group written without a `conjunction`
is still a group, and reads as `and`.

`modelValue` is required and the component holds nothing of its own: an edit is
an emit, and a host that drops it renders a tree that does not move. `null` is
an empty tree, which is what a nullable backend field bound straight to
`v-model` arrives as, so the only thing left for a missing prop to mean is a wiring
mistake, which is worth failing on.

### One operator per group

A group holds one `and` or `or` and joins every one of its children by it, so a
level reads `A and B and C` and never `A and B or C`. A rule that mixes them is
spelled by nesting, as `A and (B or C)`, which is the only spelling of it a
reader has to learn, and the one the brackets on screen already show.

The operator sits on a rule drawn down the start edge of the group, so what it
joins is visible rather than inferred from the row it happens to sit on. Every
row after the first shows it, including the row a nested group's card sits in.
A card with nothing in that cell reads as unattached.

**Only the first gap is a control.** The cell on row 1 is the and/or button;
every cell below it repeats the same word as plain text, because there is only
one value and a second button for it would read as per-gap editing to anyone who
found the lower one first. Text rather than a disabled button, for the reason
`readonly` gives: a disabled control is skipped in a screen reader's forms mode
and is exempt from the contrast minimum, so a group of eight would be read as
one operator and seven blanks.

This is what CRM, Helpdesk and LMS each write by hand today through
`#condition-conjunction`. The slot stays, for restyling the cell, but a host no longer needs
it to get uniform behaviour, and `setGroupConjunction` is exported for a host
that wants to write the operator from somewhere else entirely, a group header of
its own, say:

```vue
<template #conjunction="{ conjunction, groupPath, canToggle, toggle }">
  <Button v-if="canToggle" :label="conjunction" @click="toggle" />
  <span v-else>{{ conjunction }}</span>
</template>
```

Ungrouping is where the one-operator rule costs something. A nested `or` group
spliced into an `and` parent is re-joined by the parent's operator, because that
is the only one its new level has. That is what taking the brackets off would
mean if the rule were written out, and the same thing the menu item says it
does.

### Rows taller than one line

A row is as tall as its condition, and a condition is free to grow: a hint under
a control, a wrapped value, a second row of inputs. The operator, the drag handle
and the actions menu are anchored to the row's **first line** rather than centred
in it, so a condition that grows downward does not carry its operator halfway
down beside nothing.

The first line is assumed to be one control tall, which is what the built-in leaf
renders. A `#condition` slot that leads with something taller, say visible field
labels above its controls, will show the operator beside that instead. Use
`#condition-where` / `#condition-conjunction` to place it yourself in that case; they exist for it.

A row holding a nested group is the one row whose first line is not at its top
edge, and the component accounts for it: the card draws its own border and
padding, so the first line of that row is the first rule _inside_ the card, and
the operator, handle and menu drop to meet it. A card's operator belongs beside
the rule it introduces, not beside the card's empty top corner. Under
`bordered="root"` or `"none"` there is no card and so no drop.

### Nesting is always inline

Every group renders in place, at every depth. There is no dialog and no
`modalDepth`: a group deep enough to be cramped is still a group on the page,
drawn where it sits.

**The cost is width, and at `maxDepth` 4 it is severe.** A nested group sits in a
row of its parent, so each level spends that row's leading tracks before the
group's own contents start: the conjunction cell (`minmax(66px, max-content)`),
the drag handle (`w-4`), the two `gap-x-2`s between them, and, under
`bordered="all"`, the card's own `border` and `p-3`. That is **111px of start
edge per level**, and the innermost leaf row then spends another 98px on its own
conjunction cell and handle before its field control begins.

At the default `maxDepth` of 4 that is roughly **540px gone before the deepest
row's first cell**, with the card paddings taking another ~50px off the end. In
a form column around 600px wide there is nothing left: the three content-sized
cells collapse to their `minmax(0, …)` floor and the row wraps rather than
overflowing. This is exactly the problem `modalDepth` existed to solve, and
removing it is a deliberate trade. The component stops carrying a second
rendering mode, and a host that needs the width back has three ways to get it:
lower `maxDepth`, set `bordered="root"` or `"none"` (which returns the 26px per
level the cards cost), or wrap the whole builder in a dialog of its own. The
last is a host's answer to "this form is too narrow", not a mode here with its
own answers for focus, teleporting, and what a drag may cross.

**Opening a deep group in a dialog is a host recipe now, rather than a prop.**
`#group` hands the host the default rendering as a component, so the host writes
the dialog it wants and puts the real group in its body: the same tree, the same
context, the same announcements, and not a second builder.

Render the tree in **tiers** and the width cost stops compounding. At a tier of
3, depths 0-2 are on the page, a group at depth 3 opens a dialog holding 3-5,
and one at depth 6 opens another holding 6-8. Each dialog starts back at the
left edge, so no row is indented more than one tier, which is what makes
`maxDepth: 8` usable.

```vue
<script setup lang="ts">
/** How many levels share one surface. Host state, not a prop. */
const tier = 3

/** True only where a tier starts: one dialog per tier, not one per level. */
const startsTier = (depth: number) => depth % tier === 0

/**
 * The open tiers, outermost first. A STACK, not a single path: a tier past the
 * second is opened from INSIDE the dialog of the tier above it, so writing one
 * path would close that dialog, and with it the button just clicked. The inner
 * dialog appears to shut the instant it opens.
 */
const openTiers = ref<string[]>([])
const key = (path: number[]) => path.join(".")

const isTierOpen = (path: number[]) => openTiers.value.includes(key(path))

function openTier(path: number[]) {
  if (!isTierOpen(path)) openTiers.value = [...openTiers.value, key(path)]
}

/** Closing a tier closes every tier opened from inside it. */
function setTierOpen(path: number[], open: boolean) {
  if (open) return openTier(path)
  const at = openTiers.value.indexOf(key(path))
  if (at !== -1) openTiers.value = openTiers.value.slice(0, at)
}
</script>

<template>
  <ConditionBuilder v-model="tree" :fields="fields" :max-depth="8" bordered="root">
    <template #group="{ path, depth, Group }">
      <component :is="Group" v-if="!startsTier(depth)" />

      <template v-else>
        <Button label="Open nested conditions" @click="openTier(path)" />
        <!-- The Dialog goes INSIDE the slot. It teleports its DOM to <body>, but
             Vue resolves provide/inject up the component tree rather than the
             DOM, so the group inside it is still inside this builder. Stashing
             `Group` in a ref and rendering it outside the builder throws. -->
        <Dialog
          :open="isTierOpen(path)"
          :title="`Depths ${depth}-${depth + tier - 1}`"
          size="3xl"
          @update:open="setTierOpen(path, $event)"
        >
          <component :is="Group" />
        </Dialog>
      </template>
    </template>
  </ConditionBuilder>
</template>
```

Three things the recipe does not get for free, and they are exactly what a prop
here would have had to answer the same way for every host:

- The operator beside a collapsed group drops 13px under `bordered="all"`, which
  is the card's border and padding. The component cannot know the slot stopped
  drawing a card. `bordered="root"` or `"none"` removes the drop.
- A collapsed group's list is not in the DOM, so nothing can be dragged into it
  until it is open. Tiering makes this cheaper than a dialog per level: there is
  one boundary every `tier` levels rather than one at every level past a
  threshold.
- The builder's `role="status"` region is outside the dialog, and `aria-modal`
  hides it while the dialog is open. A host that needs edits made inside the
  dialog announced puts its own live region in it.
- Tiers nest, so the open ones are a stack. reka-ui's `DialogRoot` handles the
  nesting and each layer keeps its own focus trap, but the host owns the state:
  hold one path and opening an inner tier unmounts the outer dialog rendering
  it, which reads as the inner dialog closing the moment it opens.

## Reordering

`reorderable: true` puts a drag handle beside the operator, and a drag announces
where the row came from and where it landed. It is off by default, so a flat
filter does not have to opt out.

Dragging is the only built-in path, so it is pointer-only. `#condition-actions` is handed
`moveUp` / `moveDown` and their guards, so a host that needs a keyboard path puts
its own items in that menu; they run the same edit and announce the same
sentence.

A move within a group cannot change what a rule matches. The group's one
operator joins every pair alike, so every arrangement of `A or B or C` is still
`A or B or C`. There is no gap for a reorder to re-point.

### Rows move between groups

A row can also be dragged **out** of its group: into a sibling group, into a
nested one, or back out to an ancestor. Every list in one builder shares a
Sortable group named after the builder, so two builders on a page cannot
exchange rows.

Reparenting does change what a rule matches, since the row is joined by its new
group's operator rather than its old one. That is the edit, not a side effect.
It is what dropping a rule inside a bracket means.

Three things refuse a drop, and they refuse it **during** the drag, so there is
no drop indicator and nothing lands and snaps back:

- a drop whose subtree would sit deeper than `maxDepth`. The whole subtree
  travels, so a group two levels deep needs two levels of room, not one; a leaf
  adds no level and is never refused on depth.
- a group dropped into itself or into anything it contains, which would detach
  that subtree from the tree entirely.
- anything, while `reorderable` is false. It turns off dragging between groups
  as well as within them, since both are this one edit.

A group left empty by a row leaving goes, cascading up, exactly as it does when
its last row is removed. The root never goes: an empty root is the empty state.

Grouping is still an explicit `Turn into a Group` / `Add Condition Group`.
Dropping a row **on** a nested group's card does not put it inside; you drop it
into the card's list.

A drop is announced like a menu move, except that a reparent says it landed in
another group rather than naming two positions: the position it left is in a
group the row is no longer in, and reading it out beside the new one would
describe a reorder that did not happen.

## Operators

Reading is wider than writing: the reader accepts every operator the stored
format can hold, and a leaf keeps a stored operator in its own dropdown even
when the field's own operator list would not offer it today, so a saved rule is
always legible, and is only rewritten deliberately.

Writing is narrower than `Filter`'s list. `is not` is offered because the host's
compiler implements it; `timespan` is withheld because the host's compiler has
no rule for it and would emit an expression that raises whenever the rule runs.

## Persisting

Frappe's Assignment Rule and SLA condition fields store an array that interleaves
conjunctions between conditions. Convert at the persistence boundary:

```ts
import {
  fromFrappeConditions,
  toFrappeConditions,
} from "@framework/ui/ConditionBuilder";

const tree = fromFrappeConditions(JSON.parse(doc.assign_condition_json || "[]"));
doc.assign_condition_json = JSON.stringify(toFrappeConditions(tree));
```

Separator tokens are matched case-insensitively, since a record hand-edited or
written by another tool can carry `"OR"`, and reading that as an operand would
invert the rule.

### Reading a mixed record changes what it means

The stored array carries a token per gap, so it **can** hold `A and B or C`. A
group holds one token and cannot. **On read, the first separator token on a
level wins and every other one is discarded**, so a record stored as
`A and B or C` loads, and the next save writes back, as `A and B and C`. It now
means something different, and nothing on screen says so: the rule looks like
the one the record holds.

That is accepted, not an oversight. The alternative is either reshaping a mixed
level into nested groups nobody authored, or a second editing model for a shape
the component no longer offers a way to create. Frappe's own editors write
uniform levels, so what reaches this is a record hand-edited, written by another
tool, or written by an earlier version of this component. A host with such
records to protect should compare `toFrappeConditions(fromFrappeConditions(x))`
against `x` before saving, and prompt rather than write.

The expression is compiled from the array the tree writes, so the two halves of
a record still agree with each other after a save. They just no longer agree
with what was stored.

An entry that cannot be parsed as a condition is **dropped**, along with the
conjunction beside it: an unknown operator, a doctype-qualified filter, a stray
`null`, a number or a token between two filters. The tree is what the editor
shows and what the next save writes, so such an entry is gone from the record
rather than carried through it. Nothing it could do instead is honest: it has no
row to render, no Python to compile to, and leaving it in the array while the
expression omits it makes the two halves of a record disagree.

Two things are dropped rather than written: an empty group, and a row the user
added but never gave a field to. Neither holds a condition, so both are
lossless, and both would otherwise be written as an entry the host's compiler cannot
destructure into a field, an operator and a value.

A stored `==`, `=` or `!=` is read as an alias and re-saved in this component's
vocabulary. No migration is needed: `equals`, `=` and `==` all compile to the
same `==`, so the compiled expression does not change.

### The expression

The array is what a record stores; the Python expression is what `safe_eval`
runs. A host writes both, and does not have to compile anything: bind the second
v-model and the component keeps it, compiled with the fields it already derived
from `doctype`.

Both apps name a `doctype` and let Meta supply the fields. Neither hand-builds a
`fields` array, and neither writes a compiler. What differs between them is one
prop:

```vue
<!-- CRM, an Assignment Rule over deals -->
<ConditionBuilder
  v-model="tree"
  v-model:expression="doc.assign_condition"
  doctype="CRM Deal"
/>
```

```vue
<!-- Helpdesk, an SLA over tickets -->
<ConditionBuilder
  v-model="tree"
  v-model:expression="doc.condition"
  doctype="HD Ticket"
  field-prefix="doc"
/>
```

`fieldPrefix` is not cosmetic, and it is not a preference: it is decided by what
the Python caller puts in scope, so read the caller before choosing it.

| Host | How it evaluates | What the expression must say |
| --- | --- | --- |
| Assignment Rule | `safe_eval(cond, None, doc)`, where the document **is** the locals | `status == "Open"`, no prefix |
| Notification | `safe_eval(cond, None, get_context(doc))`, a dict holding `{"doc": …}` | `doc.status == "Open"` |
| Helpdesk SLA | the same `get_context(ticket)` shape | `doc.status == "Open"` |

Get it wrong and nothing catches it: the rule saves, renders and reads back, and
raises `NameError` only when it is finally evaluated against a real document,
inside a `try`.

The same compiler is exported for a host that needs an expression away from the
control, say to compare what a stored array evaluates to:

```ts
import { toConditionExpression } from "@framework/ui/ConditionBuilder";

// doc.status == "Open" and (doc.subject and "refund" in doc.subject)
//   and (doc.priority == "High" or doc.priority == "Urgent")
toConditionExpression(tree, { fieldPrefix: "doc", fields });
```

Two rules need the fields, which is why the control passes them and a bare call
should too: a **Check** field compiles to its own truthiness (`is_open`, not
`is_open == "Yes"`, which never matches a 0/1), and a **numeric** field compiles
to a number (`total > 100`, not `total > "100"`, which raises rather than
compares). Without fields both fall back to reading the value, which is what
CRM's and Helpdesk's compilers do, and what makes a Data field holding the word
"Yes" compile as a Check.

The rules are not a `join(" and ")`. `like` compiles to a membership test
guarded on the field, `is set` to the bare field, a Check field's `== "Yes"` to
the bare field too, `between` to two comparisons, and `in` to a guarded list.
A nested group is parenthesised rather than left to Python's precedence, and an
operator with no rule, such as a legacy `timespan`, compiles to nothing rather than to
something that changes what the rule matches without saying so. `timespan` is dropped on
read as well, so it does not survive a round-trip through this component.

The expression is compiled from the array, so the two always agree about what the
record means: an entry dropped on read is absent from both, and a row with no
field is written to neither.

## Slots

| Slot | Replaces |
| --- | --- |
| `#condition` | the whole row, for a leaf of your own shape |
| `#group` | how a **nested** group renders: wrap it, or put it elsewhere |
| `#condition-value` | only the value control inside the built-in row |
| `#condition-where` / `#condition-conjunction` | the leading cell of a row |
| `#condition-actions` | the row's actions: a menu, or the single action when only one applies |
| `#add-condition` | a group's add affordance |
| `#empty` | the empty state's content |

**An empty template does not remove that furniture.** Vue renders a slot's
fallback whenever the slot produced no vnode, so `<template #where />` puts the
built-in cell straight back. Removing a piece takes a node that draws nothing;
`<template #where><span /></template>` is the smallest one. And what goes is the
content: the row still spends that cell's grid track, and the group's bracket is
still drawn through it, since both belong to the row rather than to the cell.

### `#group`

The odd one out: it does not hand over a cell, it hands over a subtree. A group
renders itself again, all the way down, and nothing a host writes can stand in
for that, so the slot is handed the default rendering **as a component**, and
what a host chooses is where to put it.

```vue
<template #group="{ group, path, depth, Group }">
  <component :is="Group" v-if="depth < 2" />
  <Button v-else :label="`${group.conditions.length} rules`" @click="open(path)" />
</template>
```

- **The root is not passed through it.** The root group is the builder itself:
  there is no row around it to keep and no ancestor to render it into, so a host
  wrapping the root is wrapping the whole control, which it does where it mounts
  it.
- **`Group` has to be rendered inside the slot.** Vue resolves `inject` and slots
  up the component tree rather than the DOM, so a dialog declared in the slot can
  teleport its markup to `<body>` and the group inside it is still inside this
  builder. Stashing `Group` in a ref and rendering it beside the builder instead
  throws, because it is a group with no builder around it.
- **It takes no props, and its identity is stable for as long as the row is**, so
  an edit anywhere in the tree does not remount the subtree, and a dialog opening
  and closing over it keeps what is inside it.
- **An empty template renders the default group**, as it does in every other
  slot here, since Vue falls back when a slot produces no vnode. A node that draws
  nothing (`<span />`) renders no group at all, which leaves the group in the
  tree, still saved, with its rows unreachable.
- **The row around the group is not the slot's.** The and/or cell, the drag
  handle and the `···` menu are the group's place in its parent, and stay the
  component's; `#condition-where`, `#condition-conjunction` and `#condition-actions` are how those are
  replaced.

## Props worth knowing

| Prop | Does |
| --- | --- |
| `expression` | write-only; `v-model:expression` gets the compiled Python |
| `fieldPrefix` | prefixes fieldnames in that expression (`doc`), nothing on screen |
| `columns` | the three cells' grid track sizes |
| `maxDepth` | how deep nesting is offered (default 4) |
| `bordered` | `all` / `root` / `none`: which groups draw a card |
| `newCondition` | factory for a new leaf, when `#condition` is used |
| `labels` | every string it renders, for `__()` |
| `readonly` | nothing is editable; the tree renders as text |
| `reorderable` | whether rows can be dragged or moved (default false) |
| `label` / `description` / `error` / `required` | the shared labeling contract every input control in this package exposes |

`readonly` shows a rule you are not editing, and is the only not-editable mode.
There is no state between it and a live builder: a form that wants its rows
fixable but not extendable, say one failing validation, puts its own control
in `#add-condition` and disables that. The reach is the same, and what "cannot be
extended" means stays the host's sentence rather than a second half-editable mode
here with its own answer for every menu item.

One add affordance is outside that slot: the empty state's button, which is what
shows when there is no group to hang `#add-condition` on. A host blocking adds on
an empty tree has nothing to replace, so it renders no builder until it does.

## Accessibility

- A group is a `<fieldset>` at the root and `role="group"` nested, named from its
  own conjunction. Nested `<legend>`s are read before every control, and a
  fixed name would state the opposite the moment the conjunction is changed. One
  operator per group is what makes that name honest for every row under it, and
  what reduces the vocabulary to "match all" and "match any".
- Only the first gap's cell is a control; the rest of the group repeats the word
  as text rather than as disabled buttons, for the same reason `readonly` does.
  That text is `ink-gray-6`, not the cell's `ink-gray-5`: gray-5 is 4.18:1 on
  white at 14px, and dropping the disabled exemption is the whole point of
  rendering it as text, so the 4.5:1 minimum has to be met once it is gone.
- Rows are a real list, so position is announced without a name to keep in sync.
- Every control is named by `aria-labelledby` against the row's field, so eight
  operator selects are told apart ("Status, operator"). Attribute fallthrough is
  not used: `Button` overwrites `aria-label` from `label`, and `Combobox` never
  passes attrs to its trigger.
- Removing a row moves focus to the row that took its place, and announces the
  count, plus the cascade when the group went with it.
- The drag handle is `aria-hidden`: it duplicates no control and names nothing.
  **Reordering has no built-in keyboard path.** A known gap, and the reason
  `#condition-actions` is handed `moveUp` / `moveDown`. Where a host adds them, the move
  announces both positions (a position alone means nothing to someone who did not
  watch it move) and returns focus to the menu it was run from.
- `readonly` renders text rather than disabled controls: a disabled control is
  skipped in a screen reader's forms mode and is exempt from the contrast
  minimum, which would make a read-only tree unreadable.

Known gap: the date and rating value controls drop attributes, so their cell
carries the name instead of the control. Fixing that needs an `aria-labelledby`
passthrough on the shared `Fields` components and frappe-ui's `DateRangePicker`.
