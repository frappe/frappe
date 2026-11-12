# Runtime rules (bindings, events, handler props, etc.)

## Bindings

- `{{ expression }}` bindings work in props, styles, and visibility.
- Keep bindings simple. Use property access and at most one short ternary.
- Put date calculations, pluralization, chained ternaries, and immediately
  invoked function expressions (IIFEs) in the page script. Define a named
  helper and call it from the binding, such as
  `{{ formatDueDate(dataItem.exp_end_date) }}`. In `setup()`, return each
  script-defined value or helper used by bindings or events.
- Inline IIFEs run again on every render of each Repeater row. They also make
  bindings difficult to read and debug.
- Store two-way v-model bindings as `{"$type": "variable", "name": "…"}` in
  prop values. These refer to page-script state. Do not use `{{ }}` for v-model.
  Expression bindings are read-only.
- In Repeater children, `dataItem` is the current row. `dataIndex` is its
  zero-based index.

## Events and handler props

- A block's event scripts are stored in `componentEvents`. Studio's AI tools
  write them with the short key `events`. A script can contain bare statements.
  Emitted values are available in `eventArgs`.
- Write a short event script inline, such as `open.value = true`. For longer
  logic, define a handler in the page script, return it from `setup()`, and
  call it from the event script, such as `saveTask()`.
- Event scripts and handler props get the raw refs. Write `count.value`.
  `{{ }}` bindings unwrap a ref, so write `{{ count }}` there.
- If the script defines `handleEvent`, the runtime calls
  `handleEvent(...eventArgs)` after evaluating the script. This example
  receives the first emitted value:
  `function handleEvent(event) { taskId.value = event.dataTransfer.getData('text') }`.
  Define `handleEvent(a, b)` for an event with two arguments.
- `$event` is Vue template syntax. It is not available in block event scripts.
- Put event modifiers on the event name. Examples include `dragover.prevent`,
  `drop.prevent`, `submit.prevent.stop`, `keydown.enter`, and `click.stop`.
  Use `.prevent` for `preventDefault` and `.stop` for `stopPropagation`.
- Handler props inside component props require arrow-function strings such as
  `"() => { … }"`. This applies to a Dialog action's `onClick` and a Dropdown or
  ContextMenu option's `onClick`. The component calls the value as a function.
  A bare statement string causes "onClick is not a function".

## Variants

Use `Variants` to compare design options during review. It renders one child
at a time. For a runtime choice, use `visibilityCondition` on each block or
bind the prop that changes.

- The Keep action keeps one option and deletes the others. Publishing a page
  that still contains `Variants` uses its first option and shows a warning.
- Each child is an option. Set its name with `variantOptionName` beside
  `componentName`. This key is not a prop. An unnamed child uses "Option N".
- Copy `variantsTemplate` and `variantOption` from
  `studio/frontend/src/utils/blockTemplate/familyTemplates.ts`. Do not write
  their structure by hand.

## Icons

- Use plain `lucide-<name>` strings for `icon`, `iconLeft`, and `iconRight`
  props and for `Icon`. There is no `getIcon()` helper or `FeatherIcon`.
- Use the `Icon` component for a standalone Lucide icon:
  `{"componentName": "Icon", "componentProps": {"icon": "lucide-<name>"}}`.
- Do not use a raw `span` with a `lucide-*` class. It has no `icon` prop, so the
  icon picker cannot appear for it.
- Use an `HTML` block for a custom SVG, such as a logo or illustration.

## Styles

- Use espresso color tokens: `var(--ink-…)` for text, `var(--surface-…)` for
  backgrounds, and `var(--outline-…)` for borders. Do not use raw hex colors or
  `rgb()`. Choose the token step by its role in the design language.
- Set a block's appearance in its style values. This keeps the properties
  visible and editable in the block's controls.
- Tailwind classes are supported only in standard apps. In a custom app, use
  style values. Text size classes and `lucide-*` icon classes work in both app
  types.
- Use a `.css` file only when block styles cannot express the rule. Examples
  include `:hover`, `:focus`, `::before`, `::after`, child or sibling selectors,
  and `@keyframes`.
