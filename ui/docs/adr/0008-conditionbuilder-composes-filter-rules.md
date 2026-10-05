# ConditionBuilder composes `Filter`'s rules and holds one conjunction per group

`ConditionBuilder` is the nested and/or condition editor behind rules that are
persisted as Frappe's interleaved condition array — an Assignment Rule's
`assign_condition_json`, an SLA's `condition_json`. Two decisions shape it.

## It composes `Filter`'s rules rather than carrying its own

A fieldtype → operator table, a default-value table and a fieldtype →
value-input dispatch already exist in this package as `Filter/operators.ts` and
`Filter/valueControl.ts`. The leaf is built over those instead of a second copy,
so the two editors cannot drift:

| Own | Reused |
| --- | --- |
| `tree.ts`, `context.ts`, `adapters.ts`, the group / row / conjunction / actions components, `ConditionLeaf.vue` | `Filter/operators.ts`, `Filter/valueControl.ts`, the shared `Fields` registry (ADR-0004) |

Reusing the value dispatch is also what lets a Link condition search its target
doctype, which a self-contained value-input table cannot do.

The row's grid markup — about forty lines — stays duplicated. `Filter.vue` has
no component test, so extracting its template would refactor code people already
use with nothing to catch a regression. The markup is cheap and visible; the
rules that drift are not, and those are shared.

### The operator vocabulary is narrower on write than on read

`Filter` queries Frappe's list API. This component writes an array that the host
application compiles into a Python expression for `safe_eval`, and the two
vocabularies differ at two points, so `conditionOperators` adjusts the shared
table rather than forking it: `is not` is offered because the compiler
implements it, and `timespan` is withheld because the compiler has no rule for
it and would emit an expression that raises every time the rule runs.

Reading is deliberately wider than writing. `fromFrappeConditions` accepts every
operator the stored format can hold, and the leaf keeps a stored operator in its
own dropdown even when the field would not offer it today, so a saved rule is
always legible and is only ever rewritten deliberately.

An entry that cannot be modelled as a fieldname/operator/value leaf at all — a
doctype-qualified filter, an unlisted operator, a stray token — is **dropped on
read**, together with the conjunction beside it so the level never re-joins on an
operator nobody wrote. An earlier design kept such an entry verbatim and
round-tripped it untouched; that is no longer true. Preserving it meant a row the
editor could not render, could not validate and could not compile, so a record
holding one was editable everywhere except in the one place it was wrong, and the
array and the expression disagreed about what the rule was. Dropping it costs
that entry and makes the two halves agree — a record is now edited without it and
saved without it, which is visible rather than silent.

### What it does not inherit

`parseFilters` drops a condition whose field is absent from Meta. Here a rule
naming a since-deleted field is kept, shown, and repairable by re-pointing its
field picker — dropping it would silently delete part of a saved rule.

The multi-value controls take `string[]` while `in` / `not in` are persisted as
a comma-separated string, and they drop a string value on the first edit. The
leaf splits it on read, option-aware, so a value whose own label contains a
comma is not split into members that match nothing. A Link's values are not
enumerable client-side, so a docname containing a comma is still split; that
residual is noted at the call site.

## A group holds one conjunction per group

`ConditionGroup` stores `conjunction: Conjunction`, one operator for the whole
level: every child is joined to the next by the same `and` or `or`. A group of
four children reads `A and B and C and D`, and `A and B or C` is not a shape it
can hold. A rule that mixes them is spelled by nesting, `A and (B or C)`.

**This reverses the original decision, which was one operator per gap**
(`conjunctions: Conjunction[]`, `conjunctions[i]` joining `conditions[i]` to
`conditions[i + 1]`). That shape matched the persisted format exactly and
round-tripped losslessly. What it did not match was any host: CRM, Helpdesk and
LMS each drove a whole group from one operator and each wrote that policy by
hand through the `#conjunction` slot, so the shape the component offered was one
nobody used and three copies of the same workaround existed to hide it.

Three things the per-gap model cost, which per-group does not:

- **A per-gap invariant**, `conjunctions.length === conditions.length - 1`, that
  every add, remove, splice and move had to maintain at every depth. Getting it
  wrong re-joined the survivors on an operator nobody picked, silently. Removing
  a row had to decide which gap died with it; a move had to carry the operator
  the row displayed to its new position. None of that code exists now.
- **A move that changes what a rule matches.** In a mixed level, which rows sit
  either side of an `or` is the rule, so dragging a row could alter it. With one
  operator per group a reorder cannot change the result at all.
- **A third accessible name.** A mixed level is neither "match all" nor "match
  any", so the labels needed a `matchMixed` that no longer has a case to state.

### The cost: reading a mixed record is lossy

The stored array still carries a token per gap, and the wire format is
unchanged — `toFrappeConditions` repeats the group's one token between every
pair, so anything written here reads everywhere it read before. But a *stored*
array can be mixed, and the tree cannot hold one.

`fromFrappeConditions` takes the **first** separator token on a level and
discards the rest. A record stored as `A and B or C` loads, and re-saves, as
`A and B and C` — silently a different rule. The alternatives were reshaping a
mixed level into nested groups nobody authored, which returns a record shaped
differently from how it was written, or keeping a second editing model alive for
a shape the component no longer offers any way to create. Frappe's own editors
write uniform levels, so what reaches this is a hand-edited record, another
tool, or an earlier version of this component. The loss is documented in the
reader's doc comment, in `ConditionBuilder.md`, and pinned by tests.

Ungrouping is lossy for the same reason at the other end: a nested `or` group
spliced into an `and` parent is re-joined by the parent's operator, because that
is the only one its new level has.

### One live cell, in the component

`setGroupConjunction` is now the only way to change an operator, and the
component applies the one-live-cell policy itself: the cell on row 1 is the
and/or button, and every cell below it repeats the word as **plain text**. Not a
disabled button — a disabled control is skipped in a screen reader's forms mode
and is exempt from the contrast minimum, which is the same rule `readonly`
follows.

The `#conjunction` slot stays, for restyling that cell. It is no longer what a
host reaches for to get uniform behaviour, which is what it had become.

## A drag may leave the group it started in

Each group's list was its own Sortable group, so a row physically could not be
dragged out of the group it was in. Grouping was an explicit menu action and a
drag could only reorder. That is reversed: every list in one builder shares a
Sortable group name, scoped to the builder id so two builders on a page cannot
exchange rows.

The tree edit is one primitive, `moveNodeToGroup`, and it is one edit — the tree
is never briefly missing the row it is carrying. Everything after the clone is
done through object references rather than paths, because the two splices
invalidate paths as they go: taking a row out of a group re-points every later
sibling, and putting it into another re-points that group's. A group emptied by
the move is pruned by identity for the same reason, and takes the same cascade
`removeNode` takes.

### Applying it once

vuedraggable is used controlled — `:model-value`, not `v-model`, committing from
the event — and a cross-group drop raises `change` **twice**: `removed` on the
source list and `added` on the target, on two different components. Each of them
holds the tree as it was before the drag, so applying both commits the second
edit on top of a tree that never had the first, and the row is duplicated or
lost depending on which lands last. Neither component can see the other half of
the move, so neither can merge them.

Sortable's `end` is the single-application path: it fires **once**, on the list
the drag started in, and carries `from`, `to`, `oldIndex` and `newIndex` in one
event — the whole move, in one component. It also fires last, after vuedraggable
has restored the DOM, so the commit is what actually moves the row. Each `<ul>`
carries a `data-group-path` for it to read the two groups off, matching the
`data-condition-path` the rows already carried.

### Refusing a drop while it is still a drop

`maxDepth` is enforced through Sortable's `put` callback, which is asked of the
group being dropped into, rather than only in the commit. A drop that would nest
too deep shows no drop indicator, instead of landing and being snapped back by a
commit that declines it. `put` and the commit call the same `canMoveInto`, so
there is one rule rather than a guard and a re-guard that can disagree.
