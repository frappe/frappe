# Plan: frappe-ui in Desk — hardening the island approach

Status: proposed · Owner: @nextchamp-saqib · Last updated: 2026-06-04

## Context

The `frappe-ui-desk-poc` branch embeds frappe-ui (Vue 3 + Tailwind 3) components
*inside* the existing Bootstrap-4 Desk as lazy-loaded **islands**. A page
controller loads a bundle that calls `mountVueIsland`
([frappe/public/js/frappe/ui/vue_island.js](frappe/public/js/frappe/ui/vue_island.js)),
which mounts a Vue app into a `data-frappe-ui` element and wires up
`SetVueGlobals`, a memory-history vue-router, a styled teleport target, theme
attrs, teardown, and hot reload.

The proof-of-concept works, but three things make it heavier than it needs to be:

1. **The build fights the bundler.** frappe-ui is a Vite-native library;
   compiling it through Frappe's esbuild pipeline needs a stack of workarounds
   (a `@vue/compiler-sfc` fs-patch, a custom `~icons/lucide` resolver,
   `import.meta.env` defines, a `typescript` expression-plugin, a vue-dedup
   resolver, a `frappe-ui` resolve plugin, and deep-path imports to dodge
   components the pinned compiler can't parse).
2. **The teleport/portal contract is piecemeal.** Overlay components (Dialog,
   Combobox, Popover, …) each teleport to `document.body` by default, which
   lands outside the styled `[data-frappe-ui]` scope. Today only some of them
   honor a host-provided target, so the fork carries per-component patches.
3. **The CSS-war machinery, while necessary, is spread across the esbuild
   pipeline** and partly duplicated (the scoped preflight is inlined into every
   island bundle).

### Constraints (decided)

- **Stay on Bootstrap Desk.** A full new Desk SPA ("D2") is a separate,
  long-shot exploration; this plan must not be a break of that size.
- **esbuild stays at `^0.28.0`** for all existing Desk bundles. The legacy
  pipeline is untouched.
- **frappe-ui is compiled from source** (prebuilt dist is not viable — most
  components are coupled to the consumer's router / provides).
- **Upstream changes to frappe-ui are allowed** and should be clean and
  general (no Desk-specific hacks left in the library).
- **The CSS-war code lives in the Frappe framework, not in frappe-ui.** Any
  Desk-isolation CSS still sitting in `frappe-ui/src/desk/*` is stale code to be
  removed upstream — the framework owns isolation.

### The one structural truth — and how we resolved it

The Tailwind-vs-Bootstrap CSS-war (scoped preflight + `[data-frappe-ui]`
scoping + `!important` stamping) is a **cascade** problem: intrinsic for as long
as frappe-ui renders into the *same cascade* as Bootstrap. A bundler change
(Vite) or dependency upgrades don't touch it. Only two things eliminate it — a
separate cascade (**Shadow DOM** / iframe) or removing Bootstrap.

**Decision (validated by spike): mount each island in a Shadow DOM.** The shadow
boundary isolates CSS both ways, so frappe-ui ships its **normal full Tailwind +
preflight** and the entire CSS-war is **deleted** — no `[data-frappe-ui]`
scoping, no scoped-preflight, no `!important` stamp. The spike confirmed the
hard risks are fine in practice: **focus trapping, keyboard nav, floating-ui
positioning, click-outside dismiss, body scroll-lock, and full-viewport
Dialogs all work** — because WS2 gave every overlay a configurable teleport
target, which we point at a node *inside* the shadow root. This supersedes the
earlier "keep the CSS-war, own it in the framework" framing in WS3.

## Goal & non-goals

**Goal:** make the island approach production-shaped by (1) building islands
with Vite, (2) standardizing one teleport contract upstream, and (3) **isolating
each island with Shadow DOM so the CSS-war is deleted, not maintained.**

**Non-goals:** replacing the esbuild pipeline for legacy bundles; a new Desk
shell SPA; removing Bootstrap.

## Architecture: two parallel build pipelines

```
                     bench build  /  bench watch
                              │
              ┌───────────────┴────────────────┐
              ▼                                 ▼
   esbuild (unchanged, ^0.28)          Vite islands build (NEW)
   *.bundle.{js,ts,css,scss}           js/islands/**/*.bundle.{js,ts}
   (ignores js/islands/)               → sites/assets/.../dist
   → sites/assets/.../dist                   │
              │                              │
              └───────────────┬─────────────┘
                              ▼
                        assets.json  (one shared map)
                              │
                     frappe.require("name") resolves either
```

Islands keep the **familiar `.bundle.js` name** and live under a dedicated
directory, `frappe/public/js/islands/`. The esbuild pipeline ignores that
directory, so it never compiles an island; the Vite builder only looks there.
The directory — not a filename suffix — is what routes an entry to Vite. Because
the output is still `*.bundle.*`, `frappe.require` / `bundled_asset` resolve it
through `assets.json` with **no runtime change**. Both pipelines write to the
same `sites/assets/<app>/dist` tree and merge into the same `assets.json`.

---

## Workstream 1 — Vite island pipeline

Move island bundles off esbuild-with-patches onto a Vite build that consumes
frappe-ui the way it's designed to be consumed. This deletes essentially all the
esbuild workarounds at once.

### Deliverables — DONE (status below)

- `esbuild/build-islands.mjs` — programmatic Vite build (one build per island).
  - Entry discovery: glob `frappe/public/js/islands/**/*.bundle.{js,ts}`.
  - **IIFE output** per island (`format: 'iife'`, `inlineDynamicImports`):
    `frappe.require` injects a classic `<script>`, so islands must be IIFEs like
    esbuild bundles, not ESM. Rollup forbids `iife` for a multi-entry build, so
    each island is built on its own and its output filenames read back from the
    returned RollupOutput (no manifest).
  - `@vitejs/plugin-vue` (latest `@vue/compiler-sfc`).
  - Inline framework-owned lucide plugin (Vite analog of
    `esbuild/lucide-icons.js`) — no `unplugin-auto-import` / `-vue-components`
    (they'd write `*.d.ts` litter; islands import explicitly).
  - `resolve.dedupe: ['vue','vue-router', '@vue/*']`; alias `frappe-ui/src/*`
    (past the package `exports`) + `frappe/public/*`.
  - `cssCodeSplit: false` so the stylesheet is extracted to a real `.css` file
    (iife + inlineDynamicImports otherwise injects CSS via JS).
  - PostCSS chain (the **framework-owned** CSS-war, see WS3):
    `tailwindcss(tailwind.config.desk-islands.mjs)` → `autoprefixer` →
    `esbuild/postcss-frappe-ui-important.js`.
- `esbuild/island-assets.js` — after each island build, merge its outputs into
  `assets.json` (keys `foo.bundle.js` / `foo.bundle.css`), invalidate the Redis
  `assets_json` cache, delete the superseded hashed files, and (watch mode)
  publish a `build_event`. Reuses `esbuild/utils.js`.
- `esbuild/esbuild.js` — `get_all_files_to_build` / `get_files_to_build` ignore
  `js/islands` so esbuild never compiles an island.
- `package.json` — `frappe-ui` = `link:./frappe-ui`; `vite@^5.4.21` +
  `@vitejs/plugin-vue@^5.2.4` devDeps; scripts:
  - `build:islands` = `node esbuild/build-islands.mjs --mode development`
  - `build` = `node esbuild && yarn build:islands`
  - `production` = esbuild `--production` then islands `--mode production`
  - `watch` = esbuild `--watch` **&** islands `--mode development --watch`
- Watch + hot reload: the build script, in `--watch`, updates `assets.json` and
  publishes the existing Redis `build_event` so the current client path
  (`frappe.hot_update` → `frappe.require` re-run → `mountVueIsland` swap) keeps
  working with **no client-side change**.

### Status / remaining

- ✅ Builds, exits cleanly, page loads (IIFE defines `frappe.ui.FrappeUIPoc`).
- ✅ `.bundle.js` naming kept → **no** runtime resolver changes (`assets.js`,
  `build_events.bundle.js` are untouched).
- ✅ Watch loop is identical to the esbuild watcher (verified by subscribing to
  the Redis `events` channel during rebuilds): on success it publishes
  `{success, changed_files:[js,css], live_reload}` (→ client busts `_executed`,
  refetches assets_json, fires `frappe.hot_update`, success toast); on a build
  error it publishes `{error.errors[].location, formatted, stack}` (→ BuildError
  overlay with a clickable file:line:column); honors `--live-reload`. Superseded
  hashed files are deleted each rebuild. Browser DOM hot-swap is the same
  `frappe.hot_update` path legacy bundles use — left for a visual eyeball.
- ☐ Decide `yarn watch` orchestration: the `esbuild --watch & islands --watch`
  form works under `bench` (process-group kill) but a bare Ctrl-C can orphan the
  backgrounded esbuild — see open questions.
- ☐ Delete the now-dead esbuild island workarounds once nothing uses them:
  `esbuild/lucide-icons.js`, the `compiler-sfc` fs-patch, `dedup_vue_plugin`,
  `frappe_ui_plugin`, the `import.meta.env` defines, the
  `expressionPlugins:['typescript']` option. Verify no legacy `.bundle` relies
  on them first (`frappe_ui_plugin`/dedup may be load-bearing) — remove
  surgically.

### Exit criteria

- `bench build` and `bench watch` produce a working `frappe-ui-poc` page with no
  esbuild Vue/frappe-ui patches in the path.
- Editing `FrappeUIPoc.vue` hot-swaps the island in the browser.
- Production build (`--production` equivalent) emits minified, hashed island
  assets registered in `assets.json`.

### Risks / open questions

- **Two watchers, one assets.json.** esbuild watch and Vite watch both write
  `assets.json`; serialize writes (merge, don't overwrite) to avoid races.
- **Bench integration.** `bench build`/`bench watch` ultimately call frappe's
  `yarn build`/`yarn watch`; confirm running both pipelines under one script is
  acceptable to bench (exit codes, output parsing) or whether esbuild.js should
  spawn Vite as a child instead.
- **CI / docker build** (`FRAPPE_DOCKER_BUILD`, `--using-cached`) must also run
  the islands build; mirror the cached-assets path.

---

## Workstream 2 — Unified teleport contract (upstream frappe-ui)

Replace the per-component portal patches with **one** host-provided teleport
target that every overlay honors. This is purely additive upstream and removes
the fork's bespoke portal changes.

### Design

- A single inject key (the existing `usePortalTarget()` composable is the seed —
  Combobox already uses it; Dialog takes `:to="portalTarget"`).
- Every overlay component resolves its teleport target as:
  `explicit prop  →  usePortalTarget() inject  →  reka-ui default (body)`.
- Components to bring onto the contract: **Dialog, Combobox, Popover, Select,
  Dropdown, Tooltip, Autocomplete, MultiSelect, Toast** (and TextEditor's
  popovers/suggestion/image-viewer).
- Prefer routing it through reka-ui's config/portal mechanism so it's one wiring
  point rather than N components, if reka-ui exposes a global portal target;
  otherwise a thin shared `usePortalTarget()` used by each `*Portal`.

### Framework side

- `mountVueIsland` provides the target once (it already creates a styled
  body-level `[data-frappe-ui]` portal element). Collapse the current
  string-key + `Symbol.for()` double-provide down to whatever the upstream
  contract settles on.

### Status — DONE (reka-ui overlays)

The `usePortalTarget()` composable (key `frappe-ui:portal-target`) already
existed in the clone and was consumed by **Dialog, Combobox, Select,
MultiSelect, Dropdown (+menu), Tooltip, PickerShell**. The audit found only two
reka-ui overlays still teleporting to bare `<body>`:

- ✅ **Popover.vue** — `<PopoverPortal :to="portalTarget">` + `usePortalTarget()`.
- ✅ **TimePicker.vue** — same.
- ✅ **Autocomplete** needs no direct change — it wraps `<Combobox>` + `<Popover>`,
  so it inherits the contract.
- ✅ **mountVueIsland** cleaned up: single string-key provide
  (`frappe-ui:portal-target`); dead `Symbol.for()` provide and the stale "W2
  TODO" comment removed.
- ✅ POC exercises it: added a `Popover` and `Select` to `FrappeUIPoc.vue`;
  bundle verified to contain `PopoverPortal` + the portal-target provide.

Verified every reka-ui `<*Portal>` in `src/components` now carries a `:to`.

### Out of scope for this contract (different mechanisms)

- **Toast** — uses **vue-sonner**, not a reka-ui portal. Placement is set by where
  `<ToastProvider>`/`<Toaster>` is rendered, so it's a host-placement concern,
  not a per-component inject. Handle separately when an island needs toasts.
- **Charts** — echarts `appendToBody` for tooltips (canvas-based; not affected by
  the same scoping).
- **TextEditor** popovers/suggestion — tippy.js `appendTo` (different API; and
  TextEditor isn't built in the island today).

### Remaining

- ☐ Visual check: open the Popover/Select on the POC page; confirm they render
  styled inside the island (no Bootstrap bleed, no bare-`<body>` teleport).
- ☐ Bump the framework's `frappe-ui` dep from `link:./frappe-ui` to the
  upstreamed version once these two edits are merged.

---

## Workstream 3 — Shadow DOM isolation (supersedes "own the CSS-war")

**The CSS-war is deleted, not maintained.** Each island mounts in a shadow root;
the boundary isolates CSS both ways, so frappe-ui ships its normal full Tailwind
+ preflight and nothing leaks either direction.

### Done

- ✅ [vue_island.js](frappe/public/js/frappe/ui/vue_island.js) — `attachShadow`;
  the island's stylesheet is injected **into the shadow root** (a head `<link>`
  wouldn't reach it); mount root + teleport target live inside the shadow; the
  portal target is provided as the **element** (a `#id` selector can't cross the
  shadow boundary). Teardown removes the host (drops shadow + styles + portal).
- ✅ [tailwind.config.desk-islands.mjs](tailwind.config.desk-islands.mjs) —
  dropped `important: '[data-frappe-ui]'`, `preflight:false`, `container:false`.
  Now full standard Tailwind + frappe-ui preset.
- ✅ [postcss-root-to-host.js](esbuild/postcss-root-to-host.js) — rewrites
  `:root` → `:host` so frappe-ui's design tokens land on the shadow host and
  inherit into the tree (`:root` never matches inside a shadow).
- ✅ [build-islands.mjs](esbuild/build-islands.mjs) — PostCSS chain dropped the
  `!important`-stamp, added `root-to-host`.
- ✅ Island CSS entry + page controller — preflight from `@tailwind base`; CSS
  loaded via `styleBundles` into the shadow, not the document `<head>`.
- ✅ Deleted dead `frappe/public/css/frappe-ui-scoped-preflight.css`.

Result: the **1042 `[data-frappe-ui]`-scoped, `!important`-stamped rules → 0**.

### Remaining cleanup

- ✅ **Font.** A `:root { font-family: InterVariable, … }` rule in the island CSS
  (rewritten to `:host` by `root-to-host`) gives the shadow host frappe-ui's font.
- ✅ **Removed dead esbuild island workarounds.** Deleted the frappe-ui-only
  esbuild plugins (`lucide-icons`, `dedup_vue_plugin`, `frappe_ui_plugin`) and
  the `@tailwind` + `!important`-stamp CSS wiring; deleted
  `esbuild/lucide-icons.js` + `esbuild/postcss-frappe-ui-important.js`. Kept the
  build-wide options that any bundle could use (`patchVueCompileScript`,
  `import.meta` defines, `postcss-import`, `expressionPlugins`, `autoprefixer`).
  Verified: a full `node esbuild --apps frappe` build passes (Vue bundles
  form_builder/workflow_builder + all CSS) and `desk.bundle.js` still resolves.
- ☐ **Dark mode.** Only `data-theme="light"` is wired on the host. For dark,
  set `data-theme` on the host and confirm the `:host[data-theme="dark"]` tokens
  (post `:root→:host`) resolve.

### Shadow DOM tradeoffs (for the record)

- The teleport target lives inside the shadow host (inside `.layout-main-section`),
  yet **full-viewport Dialogs still cover the navbar/sidebar** — verified in the
  spike. If a future container introduces a clipping/stacking context that breaks
  this, the fallback is a body-level shadow container for overlays.
- Per-root style cost: each island ships its own copy of the frappe-ui CSS into
  its shadow. Fine for a handful of islands; if many islands mount at once,
  switch the `<link>` injection to a shared `adoptedStyleSheets` (constructable
  stylesheet) to dedupe.

---

## Sequencing

1. **WS1 first** (Vite pipeline) — unblocks everything and is the biggest
   ergonomics win. Ship behind the existing POC page; no user-facing surface.
2. **WS3 alongside WS1** — the CSS-war relocates *into* the Vite PostCSS chain,
   so it's natural to do together. (WS1 and WS3 are one PR in practice.)
3. **WS2 in parallel/after** — upstream frappe-ui work; lands the contract and
   lets us drop the fork pin. Independent of WS1/WS3 except the final
   dependency bump.

## Validation

- Visual + interaction parity on the `frappe-ui-poc` page (buttons, all three
  dialogs, combobox dropdown) before/after each workstream.
- Bundle-CSS diff to prove WS3 changes are output-neutral.
- Confirm legacy Desk Vue (Form Builder, Workflow Builder) is untouched — they
  stay on esbuild; smoke-test one of each.
- `bench build` (production) and `bench watch` (dev + hot reload) both green.

## Open questions to resolve before coding

- Bench orchestration: one combined `yarn build` vs. esbuild.js spawning Vite —
  which does bench tolerate cleanly? (affects WS1 task 3)
- Does reka-ui expose a single global portal-target hook, or must each overlay
  be wired individually? (affects WS2 effort)
- Are `frappe_ui_plugin` / `dedup_vue_plugin` used by any non-island Vue bundle
  today? (affects what WS1 task 5 can safely delete)
