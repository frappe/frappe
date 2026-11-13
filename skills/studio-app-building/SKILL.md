---
name: studio-app-building
description: Build or edit Frappe Studio apps and pages. Covers block trees, data bindings, page scripts, design, and standard (exported) apps. Use for Studio App or Studio Page work. Excludes ordinary Vue frontends.
---

# Building Frappe Studio apps

A Studio app contains `Studio Page` documents. Each page has a JSON block tree,
optional `Studio Page Resource` rows, and page logic.

- Read [RULES.md](RULES.md) before writing bindings, events, or styles.
- Read [DESIGN.md](DESIGN.md) before building or restyling a page.
- Read [ROUTING.md](ROUTING.md) when working on navigation, redirects, guards,
  or `boot` data.
- Check `studio/frontend/src/data/components.ts` and
  `studio/frontend/src/data/componentFamilies.ts` for available components.

## Custom and standard apps

Read `is_standard` on the Studio App before editing it. This field controls
source storage, compilation, editing, and preview. Read the matching Custom apps
or Standard apps section. The later sections apply to both types unless they
name one type.

| Detail | Custom app (`is_standard` 0) | Standard app (`is_standard` 1) |
| --- | --- | --- |
| Source files | `Studio App File` records, plus each page's own `script` field | Files under `<frappe_app>/studio/<studio_app>/` |
| Compiled in the editor and preview | The browser | Vite's dev server |
| Compiled on publish | Vite, from a copy of the source files | Vite |
| Languages | `.js`, `.json`, `.css` | `.js`, `.json`, `.css` + `.ts`, `.vue` |
| Edit | In Studio, on any site | The files or Studio, in developer mode only |

## Custom apps

- Insert `Studio App` and `Studio Page` documents, or create them in Studio.
  Then write the source files.
- No build is needed while editing. After you save a file, it runs on the next
  render in the editor and preview. Publishing builds the app with Vite.
- The browser compiles and runs the source as written. A custom app rejects
  `.ts` and `.vue` files, `tsconfig.json`, Tailwind config files, and dotfiles.
  TypeScript syntax inside a `.js` file is a runtime syntax error.
- Use Studio Components for reusable layouts. Export the app if you need your
  own `.vue` files.
- The app can import `vue`, `vue-router`, `pinia`, `frappe-ui`,
  `frappe-ui/list`, `frappe-ui/charts`, and its own files. There is no npm.
  Export the app if it needs another package. Export makes the app standard.
- Preview and publishing insert CSS without changes. Use public asset URLs,
  such as `/files/logo.png`. CSS references cannot read the server filesystem.

### Module rules

- Use ESM `import` and `export`. Relative paths and `@app/` are supported.
  Dynamic `import()` requires a literal path.
- A JSON file exports its object as the default export. Its top-level keys are
  also named exports. Import CSS for its side effects. CSS has no default
  export.
- Import queries such as `?raw` and `?url` are not supported. Import fragments
  and attributes are also not supported. Use identifiers for import and export
  names. Do not use string names.
- `require`, `module`, and `exports` are not available. These names are also
  reserved as top-level bindings.
- Top-level `await` and `import.meta` are not supported. Put asynchronous work
  in `setup()` or an event handler. For cyclic imports, read imported values
  inside `setup()` instead of during module execution.

## Standard apps

- Developer mode is required to save a standard app, page, or component
  (`validate_standard_app_change`). Document saves export only in developer
  mode (`can_export`). Both checks are in `frappe/studio/export.py`.
- Create the app as standard: insert a `Studio App` with `is_standard` set to 1
  and `frappe_app` set to an installed Frappe app. `frappe_app` is mandatory
  when `is_standard` is set. The save writes the export folder. To convert an
  existing custom app, see [Switching app types](#switching-app-types).
- Files are stored under the linked Frappe app. Before creating files directly,
  inspect an existing export such as `helpdesk/studio/helpdesk/`:

  ```text
  <frappe_app>/studio/<studio_app>/<studio_app>.json
  <frappe_app>/studio/<studio_app>/studio_page/<scrubbed_title>/<scrubbed_title>.json
  <frappe_app>/studio/<studio_app>/studio_page/<scrubbed_title>/<scrubbed_title>.ts
  <frappe_app>/studio/<studio_app>/studio_components/<component_name>.json
  ```

- Page scripts are optional. Use TypeScript (`.ts`) for new page scripts. Keep
  existing `.js` files in JavaScript. Do not create both extensions for one
  module.
- In page JSON, top-level `name` is the scrubbed page title. `page_name` is the
  document ID used by Studio and the script bundle. Keep `page_name` unchanged.
- If you change a page title on disk, rename its folder, JSON file, and script
  file to match `frappe.scrub(page_title)`.
- In exported resource rows, fields such as `fields` and `filters` contain
  JSON-encoded strings.

### Sync and run

- For local editing, run `bench --site <site> watch-studio` beside
  `bench start`. `bench start` runs Studio's Vite dev server, which serves page
  scripts and vue components to the editor and preview. If the dev server is
  not running, start it with `yarn dev` in `studio/frontend`.
- The watcher imports changed app, page, and component JSON automatically. It
  finds `studio/` folders at startup. Restart it if you create a folder later.
  The watcher does not sync deletions. Vite hot-reloads page scripts and vue
  components.
- The watcher imports your edits. You do not need to run `bench migrate`.
- Saving a standard document in Studio can export it to disk. Wait for disk
  changes to sync before editing the same document in Studio. If the editor
  reports an external change, refresh before saving.

## Switching app types (standard/custom)

Both types use the same source paths. Do not copy files by hand. A copy does
not update `is_standard` or `frappe_app`.

Call `StudioApp.enable_app_export(target_app)` to make a custom app standard.
This sets `is_standard` and `frappe_app`, writes the JSON files, and moves the
source files to disk. Existing page scripts become `.js` files, the language
they were written in. Use `rename_studio_file` to change one to `.ts`.

Call `disable_app_export` to make the app custom again. A custom app cannot
keep some exported files, including `.ts` and `.vue`. If these files exist,
`disable_app_export` stops unless you confirm their deletion.

## Source files

Use the `frappe.studio.api` file APIs for source files. `list_studio_files` and
`read_studio_file` read them. `write_studio_file`, `create_studio_file`,
`rename_studio_file`, and `delete_studio_file` change them. All of these take
`frappe_app` and `studio_app` and work for both app types. A custom app does
not use `frappe_app`.

The APIs support scripts, stylesheets, and shared code. They reject writes to
the app, page, and component JSON generated by Studio. Change the document
fields for blocks, resources, and routes. In a standard app, you can also edit
the exported JSON on disk.

In a custom app, `studio_page/<scrubbed_title>/<scrubbed_title>.js` refers to
the page's `script` field. In a standard app, the page script is a file on disk
with a `.js` or `.ts` extension.

## Routes and preview

The app's `route` is its URL prefix. Page routes start with `/` and are relative
to this prefix. Each page route must be unique within the app. `app_home` holds
a page document ID.

Use `/dev/<app_route>` to preview either app type. It uses the editor's renderer
and shows draft blocks and unpublished pages. No build is needed. The user
must have read access on Studio Page.

`/<app_route>` serves the published build. Pages must be published to use this
route. Guest access also requires `allow_guest`.

## Working across an app

Read an existing page's tree before building a new sibling page. Reuse its
colors, spacing, and section structure. Complete one page before starting the
next. There should be some consistency across pages in terms of layout and
design. When you add a page, update navigation on the pages that link to it.

## Build the page

### Data

- Resources are stored in `Studio Page.resources`. Read the actual DocType
  fields before configuring a Document List or Document source. A list exposes
  `{{ source.data }}`. A document exposes `{{ source.doc }}`. Repeater children
  use `dataItem` for the current row.
- Filters accept `{"status": "Open"}` or `{"status": ["!=", "Closed"]}`.
  Use `["in", [...]]` for multiple values. Do not use a bare list.

### Blocks

`draft_blocks` holds the editor's JSON array. It contains one root block.
`blocks` holds the published copy.

```json
[
	{
		"componentId": "root",
		"componentName": "div",
		"originalElement": "body",
		"baseStyles": {"display": "flex", "flexDirection": "column"},
		"children": [
			{
				"componentId": "div-x1y2z3",
				"componentName": "div",
				"originalElement": "div",
				"baseStyles": {"padding": "20px"},
				"mobileStyles": {"padding": "12px"},
				"children": [
					{
						"componentId": "Button-a1b2c3",
						"componentName": "Button",
						"componentProps": {"label": "{{ saveLabel }}", "variant": "solid"},
						"componentEvents": {
							"click": {"action": "Run Script", "event": "click", "script": "save()"}
						},
						"componentSlots": {
							"prefix": {
								"slotName": "prefix",
								"slotContent": [
									{
										"componentId": "Icon-d4e5f6",
										"componentName": "Icon",
										"componentProps": {"icon": "lucide-check"}
									}
								]
							}
						}
					}
				]
			}
		]
	}
]
```

- Set `originalElement` to `"body"` on the root and `"div"` on containers.
  Without this field, the block and its children render blank. Do not set
  `originalElement` on component blocks.
- Each `componentId` must be unique in the page. Studio generates
  `<componentName>-<random string>`.
- `tabletStyles` works like `mobileStyles`. Both hold only the properties that
  change from `baseStyles`.
- Put a slot's blocks in `slotContent`, not directly under the slot name.
- Blocks can also have `classes`, `blockName`, and `visibilityCondition`. Follow
  an existing export when writing JSON files directly.

### Component families

Some components are a family of blocks, not one block. Examples are `List`,
`Sidebar`, `SettingsDialog`, `RadioGroup`, and the charts. The editor adds a
family as a complete working tree from a template.

- Copy the tree from the family's template in
  `studio/frontend/src/utils/blockTemplate/familyTemplates.ts`. Do not write
  its structure by hand.
- The family members and their props are in
  `studio/frontend/src/data/componentFamilies.ts`.

#### List

A `List` does not accept table-style `rows` and `columns` objects.

- Set `List.columns` to CSS grid track sizes.
- Put `ListHeader` and `ListRows` directly inside `List`.
- Bind records to `ListRows.items`. Put one `ListRow` template in the
  `ListRows` `default` component slot.
- The slot exposes `item`, `index`, and `value`. Bind cells with
  `{{ item.<field> }}`. Bind the row's `value` prop with `{{ value }}`.

## Page code

A page script is optional. It is a module, and its default export works like a
Vue component's `setup()` function, not `<script setup>`: return what the page
uses.

```js
import { ref, onMounted } from "vue"
import { createListResource, toast } from "frappe-ui"

export default function setup({ router }) {
	const search = ref("")
	const tasks = createListResource({
		doctype: "ToDo",
		fields: ["name", "description"],
		auto: true,
	})

	function openTask(name) {
		router.push({ name: "Task", params: { name } })
	}

	onMounted(() => toast.success("Ready"))

	return { search, tasks, openTask }
}
```

Vue's `setup()` rules apply:

- Return each script-defined value or handler used by bindings and events.
- Lifecycle hooks and `watch` work. Register them before the first `await`.
  Hooks registered after an `await` do not run, and watchers are not disposed
  automatically.
- `{{ }}` bindings unwrap a returned ref. Event scripts do not: write
  `search.value` there.

Studio differs from Vue in these points:

- The argument is `context`. It supplies page resources, variables, `route`,
  `router`, and `socket` (the app's socket.io connection).
- Vue and Frappe UI APIs are not injected. Import them, including `call` and
  `toast`.
- The page renders nothing until an async `setup()` resolves. Load data with an
  auto-fetching resource such as `createListResource` and return it. Use
  `await` only if the page cannot render without the result.
- Keep state in code instead of Studio variables.
- Store shared code in the app's files and import it with `@app/...`. This
  includes stores, composables, and a standard app's `.vue` components.

## Tailwind CSS

- Tailwind classes are supported only in standard apps. The editor and preview
  use the editor's stylesheet, which scans standard apps on disk but not a
  custom app's files. In a custom app, set appearance in block style values.
  Text size classes and `lucide-*` icon classes are the exception. They work in
  both app types.
- Tailwind runs at build time. Publishing builds every app and includes its
  Tailwind classes in the CSS.
- If a build fails or has not run, the app uses the shared Studio renderer.
  Its stylesheet contains only the classes included in that renderer's build.
  Publish the app again to include the app's own classes.
- In a standard app, Tailwind scans only `<frappe_app>/studio/<studio_app>/`.
  Classes in imported code outside that folder are not included. For example,
  this can affect a `shared/` package also used by the Frappe app's frontend.
- To scan extra paths in a standard app, add `tailwind.config.ts` or
  `tailwind.config.js` next to `tsconfig.json`. List the paths in `content` as
  an array of globs. Paths are relative to the config file. Studio skips
  `node_modules` in these paths.
- Studio uses only `content` and `safelist`. It ignores `theme` and `plugins`.
  The editor combines all app configs into one stylesheet. Keep `safelist`
  short. Restart the Vite dev server after adding or changing the config.

  ```js
  export default {
  	content: ["../../shared/src/**/*.{vue,ts}"],
  	safelist: ["prose-sm"],
  }
  ```

## Vue components

A standard app can use its own Vue components as blocks. A custom app cannot.
Export the app first. Choose the smallest tool that does the job:

- **Built-in component**: use it when it already does the job. Do not write a
  Vue component only to restyle a built-in component.
- **Studio Component** (`studio_components/*.json`): use it for a reusable
  layout made of ordinary blocks.
- **Vue component**: use it only when built-in components and block
  compositions cannot express the UI cleanly. This means a stateful widget (a
  rating input, a drag-and-drop board, a canvas or SVG drawing), a third-party
  library, or markup that needs dozens of blocks and heavy script glue.

To add a Vue component:

- Put the single-file component at
  `<frappe_app>/studio/<studio_app>/components/<ComponentName>.vue`.
  Studio finds `.vue` files anywhere inside `<frappe_app>/studio/<studio_app>/`.
  The file name becomes the block's `componentName`.
- The file name must be unique in the app and must not match a built-in
  component such as `Button`. Studio skips a conflicting file without showing
  an error in the editor.
- Write a normal Vue single-file component. Use Tailwind classes and espresso
  tokens from [DESIGN.md](DESIGN.md). Use one root element where possible, or
  bind `$attrs` to the element that should receive block styles.
- Set `isCustomVueComponent: true` on its block. Do not set `originalElement`.
  Props, `{{ }}` bindings, and `{"$type": "variable"}` v-model bindings work as
  they do for built-in components. Use `componentEvents` for emitted events
  and `componentSlots` for named slots:

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

- With the Vite dev server running, `.vue` file changes update the component
  panel and canvas without a restart. This includes adding and removing files.
  A page script can also import the component directly and render it with `h()`:
  `import Board from "@app/components/Board.vue"`.

## Verify

- You need not build or publish to verify a change. Do not run `bench build` or
  `build-studio-app` after an edit. The editor and preview show saved work
  without a build, including draft blocks and unpublished pages.
- Check the page in preview at `/dev/<app_route><page_route>`.
- Check desktop, mobile, and tablet styles.
- Page script, event script, and binding errors go to `console.error`. The page
  still renders. The editor also shows a page script error while that script is
  open.
- Build only to check the published route `/<app_route>`. Publish the app, or
  run `bench --site <site> build-studio-app <app_name>`.
