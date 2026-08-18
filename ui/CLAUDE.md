# UI workspace notes

## Design rules — read `PHILOSOPHY.md` first

[`PHILOSOPHY.md`](./PHILOSOPHY.md) is the design rulebook for this library — the
generative `FP*` principles that govern component APIs here (composing frappe-ui
atoms, controlled components, meta-derived options). `@framework/ui` also inherits
[frappe-ui's `PHILOSOPHY.md`](https://github.com/frappe/frappe-ui/blob/main/PHILOSOPHY.md)
(`P1`–`P14`) in full, since every component here composes frappe-ui atoms.
Walk both before drafting or refactoring a component, and cite principles by ID
(`FP1`, `P3`) in reviews. The notes below are operational specifics that support
those rules — the design *rules* themselves live in PHILOSOPHY.md, not here.

## frappe-ui vs `@framework/ui` — which package is which

The compose-atoms-don't-rebuild rule is [`FP1`](./PHILOSOPHY.md); this note is the
operational trap it depends on. This repo is **`@framework/ui`**, a slim in-house
library with only a handful of components — it is NOT the `frappe-ui` dependency.
Components imported `from "frappe-ui"` resolve to the full upstream package in
`node_modules/frappe-ui` (e.g. `apps/crm/frontend/node_modules/frappe-ui`), which
has far more (`Tabs`, `TabButtons`, etc.). Grep there, not just local `src/`,
before concluding a component doesn't exist — otherwise you'll rebuild something
that already ships upstream.

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
