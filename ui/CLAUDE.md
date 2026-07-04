# UI workspace notes

## Use frappe-ui components first; only build your own if none exists

Before hand-rolling any UI element, reach for the frappe-ui equivalent
(`Dialog`, `Button`, `Checkbox`, `Select`, `TextInput`, `Switch`, `Tabs`,
`TabButtons`, `ErrorMessage`, etc.). Only build a custom component when frappe-ui
has no equivalent — and when you do, leave a comment noting that frappe-ui lacks
it, so it's clear the custom code is a deliberate fallback rather than a missed
reuse.

Check the right package: this repo is **`@framework/ui`**, a slim in-house
library with only a handful of components — it is NOT the `frappe-ui` dependency.
Components imported `from "frappe-ui"` resolve to the full upstream package in
`node_modules/frappe-ui` (e.g. `apps/crm/frontend/node_modules/frappe-ui`), which
has far more (`Tabs`, `TabButtons`, etc.). Grep there, not just local `src/`,
before concluding a component doesn't exist.

Example: `FileUpload/FileUploadDialog.vue` uses frappe-ui's `Tabs` for its source
switcher rather than a hand-rolled tablist — `Tabs` provides the ARIA + keyboard
nav, and reka-ui's `unmountOnHide` keeps inactive panels (e.g. CameraSource)
lazy.

## Formatting

This repo's `.editorconfig` mandates **tabs** (indent_size 4, max_line_length 99) for
`*.vue`, `*.js`, `*.css`, `*.scss`, `*.html`. Prettier reads `.editorconfig`, so always
run it on changed files before committing to avoid the indentation/lint diff:

```bash
npx prettier --write $(git diff --name-only)
```

## Build stories with frappe-ui components, not raw HTML

Stories are showcases for the library — their own controls and chrome should use
frappe-ui components, not bare HTML elements. Reach for the frappe-ui equivalent
first: `Select` (not `<select>`), `Button` (not `<button>`), `TextInput`,
`Checkbox`, `Switch`, etc. `Select` takes `v-model` + an `options` array (plain
strings auto-normalize to `{ label, value }`). This keeps stories visually
consistent with the components they demonstrate and dogfoods the library.

## FormLayout fieldtypes — also update the CRM story

When adding or changing a `FormLayout` fieldtype, mirror the change in the CRM
manual-testing story at
`apps/crm/frontend/src/pages/stories/StaticSchema.story.vue` (in addition to this
repo's `src/components/FormLayout/stories/StaticSchema.story.vue`). The CRM story
is what's used to manually test fieldtypes in a real consuming app — keep the two
stories in sync. Note CRM's frontend uses **2-space** indentation (its own
prettier/eslint config), not this repo's tabs; run `npx prettier --write` from
`apps/crm/frontend` on the CRM file.

## Subagents

Offload exploration and side work to subagents to keep the main context lean.
Use them by default (don't ask) for:

- **Codebase exploration** — locating files, tracing a feature across the stack,
  finding callers/usages, reading large files for one fact. Prefer the `Explore`
  agent (read-only; returns conclusions, not file dumps).
- **Independent parallel work** — unrelated lookups/edits with no data dependency:
  launch in one message so they run concurrently.
- **Verification side-quests** — test subsets, build checks, grep sweeps whose raw
  output would flood the main context.

Keep in the main context the synthesis, the decision, and the actual fix. Relay
only what matters from a result — the user doesn't see subagent output.

Exceptions: for a single known fact (you know the file/symbol), just read it —
an agent only adds latency. Once you've delegated a search, don't also run it
yourself; wait for the result.
