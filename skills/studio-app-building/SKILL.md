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
- Read [BUILT_IN_COMPONENTS.md](BUILT_IN_COMPONENTS.md) before choosing
  components. It lists the built-in components and shows how to get the full
  props of one.

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
- Use Studio Components for reusable parts of the UI. Export the app if you
  need your own `.vue` files.
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
  <frappe_app>/studio/<studio_app>/studio_components/<component_id>.json
  <frappe_app>/studio/<studio_app>/studio_components/<component_id>.js
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
- The watcher imports changed app, page, and component JSON, and component
  scripts, automatically. It
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

A component script works the same way at `studio_components/<component_id>.js`.
A standard app scrubs the ID in the file name (`card-1` is `card_1.js`) and
exports the file only after a page uses the component.

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

Create or change one page in each tool call. A call that writes several pages
is slow to produce, can time out, and loses all of the pages when one fails.

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
		"blockName": "body",
		"originalElement": "body",
		"baseStyles": {
			"display": "flex",
			"flexDirection": "row",
			"flexShrink": 0,
			"width": "inherit",
			"overflowX": "hidden",
			"height": "100%"
		},
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

- Copy the root block from the `body` template in
  `studio/frontend/src/utils/blockTemplate/index.ts`. It has `blockName` and
  `originalElement` set to `"body"`, and the width and height that make it
  fill the page. Add the page's own styles to it, such as
  `flexDirection: "column"` for a page that stacks a header and a body.
- Set `originalElement` to `"div"` on containers. Without this field, the
  block and its children render blank. Do not set `originalElement` on
  component blocks.
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

The rules and an example block for `List` are in
[BUILT_IN_COMPONENTS.md](BUILT_IN_COMPONENTS.md).

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

## Choose a component

Choose the smallest tool that does the job:

- **Built-in component**: use it when it already does the job. Do not write a
  Vue component only to restyle a built-in component.
- **Studio Component**: use it for a reusable part of the UI that you can
  build from ordinary blocks, such as a card, a list row, a form section, or
  a sidebar that all pages share.
  Its script gives it props, state, logic, and events. See
  [Component code](#component-code).
- **Vue component**: use it only when built-in components and block
  compositions cannot express the UI cleanly. This means a stateful widget (a
  rating input, a drag-and-drop board, a canvas or SVG drawing), a third-party
  library, or markup that needs dozens of blocks and heavy script glue. Only
  a standard app can have one. See [Vue components](#vue-components).

For a Studio Component:

- Set `studio_app` on a component made for an app. Its `name` is then
  `<studio_app>/<component_id>`. A component without `studio_app` is global,
  and every app on the site can use it.
- Use the `component_id` as the block's `componentName`, such as `task_card`.
  Do not use the title in `component_name` or the document `name`. Studio
  uses the app's own component before a global one with the same id.
- A global component must work without an app's files or `.vue` components.
  Studio rejects a global component script that imports `@app/` or a relative
  path.

## Component code

A component script exports a Vue component definition with `props`, `emits`,
and `setup`. Its blocks are the template.

Pass page data through props and request page actions through events. Keep
component state and handlers in the component's own script.

```js
import { ref, computed } from "vue"

export default {
	props: {
		title: { type: String, required: true },
		size: { type: String, default: "md", meta: { control: "select", options: ["sm", "md"] } },
	},
	emits: ["select"],
	setup(props, { emit }) {
		const open = ref(false)
		const heading = computed(() => props.title.toUpperCase())

		function select(item) {
			emit("select", item)
		}

		return { open, heading, select }
	},
}
```

- Use only `props`, `emits`, and `setup`. Studio rejects other keys, such as
  `data`, `methods`, and `components`.
- `setup` gets Vue's arguments, `(props, { emit })`. It does not get the page
  `context`. Import what you need, such as `useRoute` from `vue-router`.
- Declare what a component accepts as `props` in its script. There is no other
  place: do not write `inputs` rows in the component JSON. Write `props` as a
  plain object, so the editor's form can change it. A prop's optional `meta`
  key sets the editor control (`control`: `text`, `number`, `checkbox`,
  `textarea`, `select`, `code`, or `color`), its `options`, and a
  `description`.
- **Use a Studio Component.** Set `isStudioComponent: true` on its block. The
  page sets props in `componentProps` and handles the events in `emits` in
  `componentEvents`:

  ```json
  {
  	"componentId": "task_card-ab12cd",
  	"componentName": "task_card",
  	"isStudioComponent": true,
  	"componentProps": {"title": "{{ dataItem.subject }}", "size": "sm"},
  	"componentEvents": {
  		"select": {"action": "Run Script", "event": "select", "script": "openTask(eventArgs[0])"}
  	}
  }
  ```

  An event that is not in `emits` is a DOM event of the component's root
  block.

### What a component can use

A component's blocks can use:

- The component's props, as `{{ props.title }}`, and the values that its
  `setup` returns, by name, as `{{ heading }}`. The page-code rules for
  returned values, hooks, and `await` apply.
- Slot values, such as `dataItem` and `dataIndex` in a Repeater.
- The built-in `route`, `router`, `socket`, `toast`, and `call` helpers.

A component must not read a page's variables, data sources, or functions. For
example, a component that uses `{{ tasks.data }}` needs the page to provide
`tasks`. It can fail in the component editor or on another page.

- **Pass page data through props.** Declare a `tasks` prop in the component
  script. On each page, set the component block's `componentProps.tasks` to
  `{{ tasks.data }}`. Inside the component, use `{{ props.tasks }}`.
- **Use events for page actions.** If the component needs a page function such
  as `save()`, declare `"save"` in `emits`. Return a function from `setup`
  that calls `emit("save")`, as `select` does in the example, and call it from
  the block's event. On each page, handle the event in the component block's
  `componentEvents` and call the page's `save()` there.
- **Import shared state in app components.** An app's component may import
  shared app state, such as the signed-in user, through a composable from the
  app's files. Pass page-specific data through props. A global component
  cannot import app files. Pass app-specific data to it through props.

Older components read the page directly, and some only have `inputs` rows in
their JSON. Studio still runs them. Update an older component to these rules
when you work on it: follow
`studio/frontend/docs/migrate-global-components-to-app-components.md`.

## Components on desk

A workspace is a global Studio Component: a root component whose blocks are
widget components. No Studio App is necessary.

- `Workspace.studio_component` links the root. A workspace without one has
  `content` and widget tables, and `frappe/desk/workspace_component.py`
  converts them to the same kind of tree each time the page loads.
- The widgets are standard components in the frappe repository, at
  `studio/studio_components/`:
  `desk_links`, `desk_shortcut`, `desk_number_card`, `desk_chart`, and
  `desk_quick_list`. Use them by id, with `isStudioComponent: true`.
- The root block is a grid of 12 columns. Give each child a
  `gridColumn: "span <n>"` style, and `span 12` in `mobileStyles`.
- The server applies the reader's permissions to the widget blocks before it
  sends the tree (`WidgetResolver`). It removes a widget that the reader
  cannot open. A widget that needs this check gets a resolver there.
- Open a global component with no app at `/studio/component/<component_id>`.
  Use `/studio/component/new` to make one. This works on any site.
- To ship a component in a Frappe app's source, set `frappe_app` on it in
  developer mode. Its files are then
  `<frappe_app>/studio/studio_components/<component_id>.json` and `.js`.
  `bench migrate` syncs them, and the component is standard on other sites.
- On desk, a component gets its data in its own script, such as
  `createListResource` from `frappe-ui`. The requests use the permissions of
  the user who looks at the workspace. There is no page, so `route` and
  `router` are not those of an app. Use `window.frappe.set_route(...)` to open
  a desk view.
- Every desk user can load a global component's blocks and script, except a
  workspace's root. Do not put a secret in them.
- Set appearance in block style values, as in a custom app. Desk's stylesheet
  for components has the text size classes and the `lucide-*` icon classes
  only.
- Other desk code can show a component with
  `frappe.ui.mount_island("frappe.studio.component", element, { component, props })`.

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
Export the app first. To choose between a Vue component and the other kinds,
see [Choose a component](#choose-a-component).

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
- **Use a Vue component.** Set `isCustomVueComponent: true` on its block. Do
  not set `originalElement`.
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
