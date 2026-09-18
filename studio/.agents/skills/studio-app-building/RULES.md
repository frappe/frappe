---
description: Runtime rules shared VERBATIM by both surfaces — external coding agents read this file via SKILL.md, and Studio's in-product AI bakes it into its prompts (studio/ai/prompts.py loads it at import, frontmatter stripped). Write a rule once here when it applies to both; keep rules audience-neutral — no repo paths, no tool names.
---

# Runtime rules (bindings, events, handler props)

- `{{ expression }}` bindings work in props, styles, and visibility.
- Keep `{{ }}` bindings THIN — property access plus at most one short
  ternary. Real computation (date math, pluralization, chained ternaries, any
  IIFE) belongs in the page script as a named helper the binding calls:
  `{{ formatDueDate(dataItem.exp_end_date) }}`, with `formatDueDate` declared
  in the script (custom page: a top-level function, auto-exposed; standard
  page: returned from `setup()`). An inline IIFE in a prop is unreadable,
  undebuggable, and re-evaluated on every render of every Repeater row — the
  page script is where logic lives.
- Block `events` scripts can be bare statements. Emitted values are available
  in `eventArgs`; define
  `function handleEvent(event) { taskId.value = event.dataTransfer.getData('text') }`
  to receive the first value. The
  runtime calls `handleEvent(...eventArgs)` after evaluating the script, so
  use `handleEvent(a, b)` for an event with two arguments. `$event` is Vue
  template syntax and is not available in block event scripts. For
  preventDefault/stopPropagation, put a MODIFIER
  on the event name: `dragover.prevent`, `drop.prevent`,
  `submit.prevent.stop`, `keydown.enter`, `click.stop`.
- HANDLER PROPS living INSIDE component props — a Dialog action's `onClick`,
  a Dropdown/ContextMenu option's `onClick` — are arrow-function STRINGS:
  `"() => { … }"`. The component calls the value directly, so a bare
  statement string throws "onClick is not a function". This differs from
  block `events`.
- Two-way (v-model) binds are stored as `{"$type": "variable", "name": "…"}`
  prop values, resolved against page-script state — never a `{{ }}` binding
  (those are read-only).
- Repeater children see `dataItem` (the current row) and `dataIndex` (its
  0-based index).
- Style values use espresso tokens — `var(--ink-…)` for text, `var(--surface-…)`
  for backgrounds, `var(--outline-…)` for borders — NEVER raw hex or rgb().
  Pick the exact step by ROLE from the design language.
