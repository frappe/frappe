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

An **island** is a Vue UI unit an app builds and desk mounts in a shadow root. The app
owns the bundle: an island carries its own Vue, its own frappe-ui and everything else
it imports, so nothing has to be on the page before it loads. Framework owns one seam —
a name, a URL and a `mount(el, context)` export. See
[the decisions](island/decisions/).

The pieces:

| Piece | Where |
| --- | --- |
| `mountVueIsland`, the mount contract | `@framework/ui/island` |
| `buildIslands`, the build preset | `@framework/ui/vite/island` |
| `mountIsland`, the host loop | `@framework/ui/island/host` |
| `frappe.ui.mount_island`, desk's host | framework |
| `<Island>`, a Vue app's host | `@framework/ui/island/Island.vue` |

Both hosts wrap the one loop: it imports the module a name resolves to and calls its
`mount`, and it hands back the handle at once. They differ in how a name resolves — desk
reads `frappe.boot`, `<Island>` calls the API. See
[the decision](island/decisions/0008-one-host-loop-two-hosts.md).

### 1. Write an entry — `@framework/ui/island`

```js
// apps/insights/frontend/src/islands/dashboard.js
import { mountVueIsland } from "@framework/ui/island";
import Dashboard from "./Dashboard.vue";

export const mount = (el, context) =>
  mountVueIsland(el, { ...context, component: Dashboard });
```

`mountVueIsland` opens the shadow root, adopts the island's stylesheet, mirrors desk's
theme, gives frappe-ui's overlays a portal target inside the root, and returns the
`update`/`unmount` handle desk holds. Pass `configure(app)` to register plugins and
global components, and `routes` if the island wants real navigation.

Inside a component, `useHost()` reads the ambient context the host injected — `locale`,
`timezone`, `user`, `theme`, `navigate`. The name is the seam, whichever host fills it:
inside an island CRM hosts, `useHost()` reads CRM's context. Every field is optional, so
a component still renders in a unit test.

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

All of an app's entries build together, so rollup lifts what two of them share into a
chunk both import. Output lands in `sites/assets/<app>/dist/island/`, and each entry
registers `<name>.island.js` and `<name>.island.css` in `assets.json`. These are the
keys `frappe.ui.mount_island` resolves, and they differ from the legacy `.bundle.js`
ones on purpose. Entry names share one namespace with every other app's, so prefix them
with the app.

The build runs on the app's own vite, `@vitejs/plugin-vue`, Tailwind, autoprefixer,
TypeScript and frappe-ui. All six are peer dependencies of this package.

### 3. Declare it — `hooks.py`

```python
ui_islands = {"insights.dashboard": "insights_dashboard"}
```

Desk then mounts it by name:

```js
const island = frappe.ui.mount_island("insights.dashboard", el, {
  dashboard: "sales",
  onNavigate: (route) => frappe.set_route(route),
});
island.update({ filters });
```

The third argument is Vue's render-function props object — data keys and `on*` listener
keys in one flat object, exactly what `h(Component, props)` takes. `update` merges into
it, like a re-render. See
[the decision](island/decisions/0009-an-island-takes-vues-props-object.md).

The handle comes back at once, before the module is in hand, so no caller waits to hold
what it must later release. `update` merges into the props the mount will start from, and
`unmount` cancels a load still out. `await island.ready` where a caller needs the mount to
be done: it resolves with the handle, rejects with what the load threw, and resolves after
a cancel, because nothing failed.

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

`name` is the same name `hooks.py` declares; the component resolves it through
`frappe.utils.island.get_island_assets`. The component is transparent: everything but
`name` and `context` is the island's props object, passed through verbatim, and a change
to it updates the island in place. `class` and `style` stay on the host element.
`context` is what `useHost()` reads inside the island — the same shape desk builds, minus
`theme`, which the mount contract adds. `@error` is the component's own: it fires with
the `Error` when a load fails, and the component renders nothing.

The component imports vue and nothing else, so an app on an older frappe-ui can still
host an island.

### What an island reports

An island draws no page header. It reports what a header would say, and each host draws
its own chrome from it:

- `title` — a `string` or `null`, the name of what the island shows.
- `actions` — an `Action[]`, where `Action` is `{ label, icon? }` plus either an
  `onClick` or an `href`.

An `onClick` runs in the island. An `href` is a URL — absolute or site-relative — to a
page outside the host app: the island says where the action goes, and the host decides
what a link out of the app does. A host opens it in a new tab, and may mark it as leaving
the app in its own idiom.

Desk turns them into the page title and the page menu. A frappe-ui app turns them into
its `LayoutHeader`. Both are plain events, because a host never sets either one: a Vue
host binds them with `@title` and `@actions`, and a desk caller passes `onTitle` and
`onActions`.

```js
frappe.ui.mount_island("insights.dashboard", el, {
  onTitle: (title) => page.set_title(title || __("Dashboard")),
  onActions: (actions) =>
    draw_menu(
      actions.map((a) => ({
        label: a.label,
        click: a.href ? () => window.open(a.href, "_blank") : a.onClick,
      }))
    ),
});
```

See [the decision](island/decisions/0010-an-island-reports-title-and-actions.md).

### CSS

The app ships one stylesheet for all its islands, adopted into every island's shadow
root. It carries preflight and the theme tokens, because a shadow root inherits nothing
from the document. The preset rewrites `:root`, `html` and `body` to `:host`, and puts
dark mode on `[data-theme="dark"]`.

Tailwind scans the modules the bundle is built from — the app's source and frappe-ui's
alike — which a first throwaway build discovers. There is no `content` option, because a
hand-kept list goes stale: Tailwind then writes no rule for a class in a file the list
missed, and the component renders unstyled with nothing reporting it. Under `watch` the
list is fixed at start-up, so a file imported after start-up **fails the build** instead
of rendering wrong. Restart the watch to pick it up.

Pass `tailwindPlugins` for the app's own Tailwind plugins, by module specifier. Without
them its `@container` and the like compile to nothing here while they work in its SPA.

### Overlays

Apply the reka-ui patch this package ships, or a popover opened over a dialog closes the
dialog under it:

```jsonc
"postinstall": "patch-package && patch-package --patch-dir node_modules/@framework/ui/patches"
```

[The decision](island/decisions/0007-reka-ui-is-patched-to-read-the-shadow-root.md) has
the detail.

### Icons

`~icons/lucide/<name>` works, through frappe-ui's resolver.

### Budget

`budget` sets the JS plus CSS bytes one island may load — its entry chunk, the chunks it
statically imports, and the app's stylesheet. An island over the budget makes the build
**warn**. The default is 2 MB, which is a backstop and not a target: an island rendering
one frappe-ui Button already weighs 288 kB, and Insights' dashboard island weighs 1.78 MB.
Pin `budget` to your own first clean build plus slack, where the number means something.
`forbiddenImports` is an optional app-local escape hatch that names a coupling by
specifier rather than catching it late by weight.

### Watch

`watch: true` rebuilds into the same place and registers again. Firing frappe's
`hot_update` is still to come — see the TODO in `vite/island/assets.js`.

`node ui/vite/island/tests/verify.mjs <app-frontend>` builds a fixture app's islands and
reads the output back. Name any frontend that has run `yarn install`; the fixture
borrows its tooling.

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
