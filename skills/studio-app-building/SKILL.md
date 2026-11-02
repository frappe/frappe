---
name: studio-app-building
description: Build or edit Frappe Studio apps and pages, including block trees, data bindings, page scripts, design, and exported standard apps. Use for Studio App or Studio Page work, not ordinary Vue frontends.
---

# Building Frappe Studio apps

Studio apps contain `Studio Page` documents with a JSON block tree, optional
`Studio Page Resource` rows, and page logic. Read [RULES.md](RULES.md) before
writing bindings, events, or styles. Read [DESIGN.md](DESIGN.md) before building
or restyling a page. For available components, check
`studio/src/data/components.ts` and `studio/src/data/componentFamilies.ts`.
Read [ROUTING.md](ROUTING.md) for navigation, redirects, guards or `boot` data.

## Standard vs custom apps

| Mode | Where edits live | Page script | Local workflow |
| --- | --- | --- | --- |
| Custom | Studio documents in the site database | Bare body in `Studio Page.script` | Edit and preview in Studio |
| Standard | Exported files under a linked Frappe app, synced to Studio documents | Companion `.ts` module with `setup(context)` | Edit files, run `watch-studio`, check `/dev/<app_route>` |

Use the mode already set on the `Studio App`. The script forms and editing
workflows are not interchangeable.

## Establish the app

- For a standard (exported) app, create the app and pages in Studio, then
  enable export with `StudioApp.enable_app_export(target_app)`. This sets
  `is_standard` and `frappe_app`, writes JSON, and moves existing page scripts
  into `.ts` files. Document save exports only in developer mode; see
  `studio/export.py:can_export`.
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
- Resources live in `Studio Page.resources`. Read the actual DocType fields
  before configuring a Document List or Document source. A list exposes
  `{{ source.data }}`; a document exposes `{{ source.doc }}`. Repeater children
  see `dataItem`. Filters accept `{"status": "Open"}` or
  `{"status": ["!=", "Closed"]}`; multiple values need `["in", [...]]`, not a
  bare list.

## Page code and components

- A custom (database-only) page uses a bare script body in
  `Studio Page.script`: no imports or export. Page resources and variables
  are already in scope; variables are refs.
- A standard page uses a sibling `.ts` module with
  `export default function setup(context) { ... }`. Import Vue and Frappe UI
  APIs explicitly. `context` supplies page resources, variables, `route`,
  `router`, `call`, `toast` and `socket` (the app's socket.io connection). Return every state value or handler used by bindings and events;
  keep state in code rather than Studio variables. Never mix the two script
  forms.
- Shared code for a standard app belongs under its Studio app folder and can
  be imported via `@app/...`.
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

Standard apps can use their own Vue components as blocks. Reach for one when
built-in components and block compositions can't express the UI cleanly: a
stateful widget (rating input, drag-and-drop board, canvas or SVG drawing), a
third-party library, or markup a page would otherwise rebuild from dozens of
blocks with heavy script glue. Don't use one to restyle something a built-in
component already does. For reusable layouts made of ordinary blocks, use a
Studio Component (`studio_components/*.json`) instead. Custom (database-only)
apps can't use `.vue` files.

- Put a single-file component at
  `<frappe_app>/studio/<studio_app>/components/<ComponentName>.vue`. Studio
  finds any `.vue` file under the Studio app folder, and the file name is the
  block's `componentName`.
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
