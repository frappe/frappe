---
name: studio-app-building
description: Build or edit Frappe Studio apps and pages, including block trees, data bindings, page scripts, design, and exported standard apps. Use for Studio App or Studio Page work, not ordinary Vue frontends.
---

# Building Frappe Studio apps

Studio apps contain `Studio Page` documents with a JSON block tree, optional
`Studio Page Resource` rows, and page logic. Read [RULES.md](RULES.md) before
writing bindings, events, or styles. Read [DESIGN.md](DESIGN.md) before building
or restyling a page. For available components, check
`studio/frontend/src/data/components.ts` and
`studio/frontend/src/data/componentFamilies.ts`.
Read [ROUTING.md](ROUTING.md) for navigation, redirects, guards or `boot` data.

## Database vs repository apps

An app's source files live in one of two places. Both hold the same files in
the same layout and author the same page scripts, so moving between them is a
file copy.

| Mode | Where the files live | Compiled by | Local workflow |
| --- | --- | --- | --- |
| Database | `Studio App File` records in the site database | The browser | Edit and preview in Studio, on any site |
| Repository (`is_standard`) | Exported files under a linked Frappe app | Vite | Edit files, run `watch-studio`, check `/dev/<app_route>` |

A database app can import `vue`, `vue-router`, `pinia`, `frappe-ui`,
`frappe-ui/list`, `frappe-ui/charts` and its own files — there is no npm.
Needing anything else is the signal to export the app to a repository.

## Establish the app

- For a standard (exported) app, create the app and pages in Studio, then
  enable export with `StudioApp.enable_app_export(target_app)`. This sets
  `is_standard` and `frappe_app`, writes JSON, and moves existing page scripts
  into `.ts` files. Document save exports only in developer mode; see
  `frappe/studio/export.py:can_export`.
- Files live under the linked Frappe app. Inspect an existing export such as
  `frappe/studio/note/` before creating them directly:

  ```text
  <frappe_app>/studio/<studio_app>/<studio_app>.json
  <frappe_app>/studio/<studio_app>/studio_page/<scrubbed_title>/<scrubbed_title>.json
  <frappe_app>/studio/<studio_app>/studio_page/<scrubbed_title>/<scrubbed_title>.ts
  <frappe_app>/studio/<studio_app>/studio_components/<component_name>.json
  ```

- The `.ts` file is optional. In page JSON, top-level `name` is the scrubbed
  title; `page_name` is the real document ID used by Studio and the script
  bundle. Keep `page_name` stable. If the title changes on disk, move the JSON
  and `.ts` file to the new `frappe.scrub(page_title)` stem. Resource fields
  such as `fields` and `filters` are JSON encoded strings in exported child
  rows.
- The app `route` is the URL prefix; page routes start with `/` and are
  relative to it. `app_home` holds a page document ID. Public routes require
  published pages; guest access also requires `allow_guest`.

## Build the page

- `draft_blocks` holds the editor's JSON array with one root block; `blocks`
  holds the published copy. Every root/container needs `originalElement`
  (`"body"` for the root, `"div"` for containers) or it and its children will
  render blank. Component blocks must not have `originalElement`.
- Stored JSON uses `componentName`, `componentProps`, `baseStyles` /
  `mobileStyles` / `tabletStyles`, `componentSlots`, `children`,
  `componentEvents`, and unique `componentId` values. AI tools use compact
  aliases such as `name`, `props`, `style`, and `c`; use an existing export as
  the model when writing JSON files directly.
- `componentSlots` maps a slot name to an object, not to a list of blocks:
  `{"default": {"slotName": "default", "slotContent": [ ... ]}}`. Studio reads a
  slot's blocks from `slotContent`.
- Resources live in `Studio Page.resources`. Read the actual DocType fields
  before configuring a Document List or Document source. A list exposes
  `{{ source.data }}`; a document exposes `{{ source.doc }}`. Repeater children
  see `dataItem`. Filters accept `{"status": "Open"}` or
  `{"status": ["!=", "Closed"]}`; multiple values need `["in", [...]]`, not a
  bare list.

## Page code and components

- Every page script is a module with
  `export default function setup(context) { ... }`. Import Vue and Frappe UI
  APIs explicitly. `context` supplies page resources, variables, `route`,
  `router`, `call`, `toast` and `socket` (the app's socket.io connection).
  Return every state value or handler used by bindings and events; keep state
  in code rather than Studio variables. `setup()` runs inside a component
  instance, so `onMounted` and the other lifecycle hooks work. Load data with
  an auto-fetching `createResource` and return it, so the page paints before
  the data lands; `await` in setup only when the page cannot render without
  it, and then register hooks and `watch` before the first `await`. After an
  await the script is outside the instance, so a hook never fires and a
  watcher is never disposed, as in any Vue `async setup()`. A database app
  stores the module in `Studio Page.script`; a repository app in a sibling
  `.ts` file.
- Shared code (stores, composables, `.vue` components) lives in the app's own
  files and is imported via `@app/...`, wherever those files are stored.
- Tailwind runs at build time, and every app is built on publish, so the built
  CSS carries the app's own classes. An app whose build failed or has not run
  yet falls back to the shared Studio renderer, which only carries the classes
  that stylesheet was built with. Publish the app again to get its own CSS.
- Tailwind only scans files inside the `studio/` app folder. If the app imports
  code from outside that folder (for example a `shared/` package that the
  Frappe app's frontend also uses), Tailwind classes used in that code will not
  be in the built CSS. To fix this, add a `tailwind.config.js` next to
  `tsconfig.json` and list the extra paths in `content`. Paths are relative to
  the config file. `node_modules` is skipped automatically. Only `content`
  (an array of globs) and `safelist` are used; `theme` and `plugins` are
  ignored. The editor combines every app's config into one stylesheet, so
  keep `safelist` short. Restart the Vite dev server after adding or changing
  the file.

  ```js
  export default {
  	content: ["../../shared/src/**/*.{vue,ts}"],
  	safelist: ["prose-sm"],
  }
  ```

## Custom Vue components

An app can use its own Vue components as blocks. Reach for one when
built-in components and block compositions can't express the UI cleanly: a
stateful widget (rating input, drag-and-drop board, canvas or SVG drawing), a
third-party library, or markup a page would otherwise rebuild from dozens of
blocks with heavy script glue. Don't use one to restyle something a built-in
component already does. For reusable layouts made of ordinary blocks, use a
Studio Component (`studio_components/*.json`) instead.

- Put a single-file component at `components/<ComponentName>.vue` — in the
  file store for a database app, under `<frappe_app>/studio/<studio_app>/`
  for a repository app. Studio finds any `.vue` file in the app, and the file
  name is the block's `componentName`. A database app compiles it in the
  browser, which has no preprocessors: `<style lang="scss">` and `lang="tsx"`
  are rejected, plain CSS and `lang="ts"` work.
- Write it like any vue single-file component. Style
  with Tailwind classes and espresso tokens per [DESIGN.md](DESIGN.md), and
  try to keep one root element (or bind `$attrs` onto it) so block styles apply.
- Reference it from a block with `isCustomVueComponent: true` and no
  `originalElement`. Props, `{{ }}` bindings, `{"$type": "variable"}` v-model
  binds, `componentEvents` for its emits, and `componentSlots` for its named
  slots all work as they do for built-in components:

  ```json
  {
  	"componentId": "RatingInput-ab12cd",
  	"componentName": "RatingInput",
  	"isCustomVueComponent": true,
  	"componentProps": {"max": 5, "modelValue": {"$type": "variable", "name": "rating"}},
  	"componentEvents": {
  		"change": {"action": "Run Script", "event": "change", "script": "saveRating()"}
  	}
  }
  ```

- With the Vite dev server running, adding, removing, or editing a `.vue`
  file updates the editor's component panel and canvas without a restart. A
  page `.ts` script may also import it directly
  (`import Board from "@app/components/Board.vue"`) to render it with `h()`.

## Sync, run, and verify

- For local standard app editing, run Studio's Vite dev server and
  `bench --site <site> watch-studio`. The watcher imports changed app, page,
  and component JSON automatically. It discovers `studio/` folders at startup,
  so restart it if the target folder was created later. Vite hot-reloads page
  `.ts` files; the watcher does not sync deletions.
- Inspect the Vite-served `/dev/<app_route>` preview and its page routes.
  Preview can show draft blocks without publishing or building. Do not run
  `bench migrate` or `build-studio-app` in the edit-and-preview loop. Build
  only when production assets or the built route need verification.
- A Studio save can export a standard document back to disk. Let disk changes
  sync before editing that document in Studio; if the editor reports an
  external change, refresh before saving.

## Working across an app

Keep sibling pages visually consistent: read an existing page's tree before
building a new one and reuse its palette, spacing rhythm, and section
structure. Routes start with `/` and are unique within the app. Build one
page at a time, completely, before starting the next; wire navigation on the
page that links to a new page, not just the new page itself.
