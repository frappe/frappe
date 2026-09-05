# @framework/ui

Shared Vue components and utilities for Frappe apps that depend on the backend. This is an extension of frappe-ui for framework specific components that all apps need. Lives at `frappe/ui` in framework and is consumed by other apps (studio, builder, hrms, …) as a local package - **never published to npm**.

Code is shipped as raw `.vue`/`.ts` source (no build step) and compiled by the consuming app's bundler, exactly like `frappe-ui`. `vue`, `vue-router` and `frappe-ui` are **peer dependencies** so the host app's single copy of each is reused — this avoids
duplicate Vue instances and mismatched router contexts.

## Consuming this package from another Frappe app

Frappe apps are independent git repos sitting side by side under the bench `apps/`
folder, so the package is linked by **relative path** using yarn's `link:` protocol
(a symlink — not `file:`, not a registry install). Three small changes in the
consuming frontend:

### 1. Declare the dependency — `package.json`

```jsonc
{
  "dependencies": {
    "@framework/ui": "link:../../frappe/ui"
  }
}
```

The path is relative to the file's own directory. From `studio/frontend` that is
`../../frappe/ui`; adjust the `../` depth for your app. Then:

```bash
yarn install   # creates node_modules/framework/ui -> ../../frappe/ui
```

### 2. Resolve the import for TypeScript — `tsconfig.json`

`moduleResolution: node` does not read the package `exports` map, so map the specifier
to source (relative to `baseUrl`):

```jsonc
"paths": {
  "@framework/ui": ["../../frappe/ui/src/index.ts"],
  "@framework/ui/island": ["../../frappe/ui/island/index.js"],
  "@framework/ui/*": ["../../frappe/ui/src/*"]
}
```

The `paths` key must match the package name `@framework/ui` (also the key under
`dependencies`) so the specifier resolves the same way in TypeScript and the bundler.

The wildcard maps a subpath into `src/`, which is where every component lives. The mount
contract does not, so it needs the entry above it. `moduleResolution: bundler` reads the
`exports` map and needs neither.

The host app must already provide the peers (`vue`, `vue-router`, `frappe-ui`) — every
Frappe frontend does.

### 3. Add the bundled Vite plugin — `vite.config.js`

```js
import frameworkUI from "@framework/ui/vite";

export default defineConfig({
  plugins: [frameworkUI()], // pass { dedupe: [...] } to add app-specific singletons
});
```

The plugin does two things, both consequences of raw source compiled in place by the
host bundler:

- **Dedupes shared singletons.** Bare imports of `vue`, `vue-router`, `frappe-ui`,
  `reka-ui` and `dompurify` resolve by realpath into a _second_ copy unless deduped —
  breaking provide/inject context (reka-ui especially) and doubling Vue.
- **Resolves this package's own dependencies against the host app.** `leaflet`,
  `cropperjs` and the rest are declared in this package's `package.json`, but a bench
  installs `node_modules` beside the host frontend and never beside the frappe repo,
  so walking up from this package's realpath finds nothing. The plugin re-runs the
  host's resolver for bare specifiers Vite could not resolve itself.

## Usage

```vue
<script setup lang="ts">
import { Link } from "@framework/ui";
</script>

<template>
  <Link doctype="User" v-model="owner" />
</template>
```

Subpaths work too (via the `./*` export), e.g. `import { FormLayout } from '@framework/ui/FormLayout'`.

## Desk islands

An **island** is a Vue UI unit. An app builds it, and a host mounts it in a shadow root. The app owns the bundle. The island carries its own Vue, its own frappe-ui and everything else it imports, so the page needs nothing loaded before the island. Framework owns one **seam**, the contract between a host and the app: a name, a URL and a `mount(el, context)` export. See [the decisions](island/decisions/).

The pieces:

| Piece | Where |
| --- | --- |
| `mountVueIsland`, the mount contract | `@framework/ui/island` |
| `buildIslands`, the build preset | `@framework/ui/vite/island` |
| `mountIsland`, the host loop | `@framework/ui/island/host` |
| `frappe.ui.mount_island`, the desk loader | framework |
| `<Island>`, the Vue host | `@framework/ui/island/Island.vue` |

The desk loader and `<Island>` wrap the one host loop. They differ only in how they resolve a name. See [decision 0008](island/decisions/0008-one-host-loop-two-hosts.md).

### 1. Write an entry — `@framework/ui/island`

```js
// apps/insights/frontend/src/islands/dashboard.js
import { mountVueIsland } from "@framework/ui/island";
import Dashboard from "./Dashboard.vue";

export const mount = (el, context) =>
  mountVueIsland(el, { ...context, component: Dashboard });
```

`mountVueIsland` opens the shadow root, adopts the app's stylesheet, mirrors the host theme, gives frappe-ui's overlays a portal target inside the root, and returns the handle. Pass `configure(app)` to register plugins and global components. Pass `routes` if the island needs navigation of its own.

Inside a component, `useHost()` returns the host context: `locale`, `timezone`, `user`, `theme`, `navigate`. Every field is optional, so a component still renders in a unit test.

### 2. Build it — `@framework/ui/vite/island`

```js
// apps/insights/frontend/build-islands.mjs
import { buildIslands } from "@framework/ui/vite/island";

await buildIslands({
  app: "insights",
  root: import.meta.dirname,
  entries: {
    insights_chart: "src/islands/chart.ts",
    insights_dashboard: "src/islands/dashboard.ts",
  },
  production: process.argv.includes("--production"),
  watch: process.argv.includes("--watch"),
});
```

One build takes all of an app's entries, so Rollup shares chunks between them. Output lands in `sites/assets/<app>/dist/island/`. Each entry registers `<name>.island.js` and `<name>.island.css` in `assets.json`. These are the keys the desk loader resolves. Entry names share one namespace with every other app, so prefix them with the app.

The build runs on the app's own Vite, `@vitejs/plugin-vue`, Tailwind, autoprefixer, TypeScript and frappe-ui. All six are peer dependencies of this package. See [decision 0005](island/decisions/0005-the-preset-resolves-its-tooling-from-the-app.md).

### 3. Declare it — `hooks.py`

```python
ui_islands = {"insights.dashboard": "insights_dashboard"}
```

The value is the bundle name, which is the key the build registers. Desk then mounts the island by name:

```js
const island = frappe.ui.mount_island("insights.dashboard", el, {
  dashboard: "sales",
  onTitle: (title) => frappe.utils.set_title(title),
});
island.update({ filters });
```

The third argument is the island's props object. The header of `island/host.js` defines its shape and the handle. See [decision 0009](island/decisions/0009-an-island-takes-vues-props-object.md).

### Hosting an island from a Vue app

A frappe-ui app hosts the same island with `<Island>`:

```vue
<script setup>
import Island from "@framework/ui/island/Island.vue";
</script>

<template>
  <Island
    name="insights.dashboard"
    :dashboard="dashboard"
    :context="{ user, locale, navigate }"
    @title="title = $event"
    @actions="actions = $event"
    @navigate="router.push($event)"
  />
</template>
```

`name` is the name `hooks.py` declares. The component resolves it through `frappe.utils.island.get_island_assets`. Every attribute but `name` and `context` is the island's props object. A change to it updates the island in place. `class` and `style` stay on the host element. `context` is what `useHost()` returns inside the island. The mount contract adds `theme` to it. `@error` fires with the `Error` when a load fails, and the component then renders nothing.

The component imports Vue and nothing else, so an app on an older frappe-ui can still host an island.

### What a page island reports

A page island fills a page. It draws no page header. It reports two things, and each host sets its own **chrome** from them. Chrome is the page title and the page menu around the island.

- `title`, a `string` or `null`.
- `actions`, an `Action[]`. An `Action` is `{ label, icon? }` plus either an `onClick` or an `href`.

An `onClick` runs in the island. An `href` is a URL to a page outside the host app. The host decides what a link out of the app does. Desk opens it in a new tab.

Both are plain events. A Vue host binds `@title` and `@actions`. A desk caller passes `onTitle` and `onActions`. An island that fills less than a page reports neither. See [decision 0010](island/decisions/0010-a-page-island-reports-title-and-actions.md).

### CSS

The app ships one stylesheet for all its islands. Tailwind scans the modules the bundle is built from, so there is no `content` option. Under `watch` the scan list is fixed at start-up. A file imported after start-up **fails the build**. Restart the watch to scan it. See [decision 0003](island/decisions/0003-tailwind-scans-the-module-list-not-a-glob.md) and [decision 0004](island/decisions/0004-an-app-ships-one-island-stylesheet.md).

Pass `tailwindPlugins` for the app's own Tailwind plugins, by module specifier. Without them, the app's `@container` variants compile to nothing.

### Overlays

Apply the reka-ui patch this package ships. Without it, a popover opened over a dialog closes the dialog under it:

```jsonc
"postinstall": "patch-package && patch-package --patch-dir node_modules/@framework/ui/patches"
```

See [decision 0007](island/decisions/0007-reka-ui-is-patched-to-read-the-shadow-root.md).

### Icons

`~icons/lucide/<name>` works, through frappe-ui's resolver.

### Budget

`budget` sets the JS plus CSS bytes one island may load: its entry chunk, the chunks it statically imports, and the app's stylesheet. An island over the budget makes the build **warn**. The default is a backstop, not a target. `DEFAULT_BUDGET` in `vite/island/index.js` records the measurements behind it. Pin `budget` to your own first clean build plus slack. `forbiddenImports` names an import that fails the build.

### Watch

`watch: true` rebuilds into the same place and registers again. A rebuild does not fire frappe's `hot_update` yet. See the TODO in `vite/island/assets.js`.

`node ui/vite/island/tests/verify.mjs <app-frontend>` builds a fixture app's islands and reads the output back. Name any frontend where `yarn install` ran. The fixture borrows its tooling.

## Adding to the package

1. Create the component/utility under `src/`.
2. Re-export it from [`src/index.ts`](src/index.ts) (`export { Foo } from './components/Foo'`).

## Notes & troubleshooting

- **"Failed to resolve import '@framework/ui'"** after a rename or fresh link: re-run
  `yarn install` and restart the dev server so the new symlink enters Vite's module graph.
  Also confirm the import specifier matches the package name `@framework/ui`.
- **A build that fails on an asset import** from one of this package's own dependencies
  (e.g. leaflet's marker images) while the dev server passes: the host app is missing the
  plugin from step 3, and only a stray `apps/frappe/ui/node_modules` was hiding it. Vite
  keeps a project-root resolution fallback for JS but not for `css` and `?url` asset
  imports, so those are the first to break on a fresh setup.
- **`vue`/`vue-router`/`frappe-ui` imports inside this package** are resolved by the host
  app (peers + `resolve.dedupe`), so the package cannot be built or type-checked in
  isolation — work on it from within a consuming app.
