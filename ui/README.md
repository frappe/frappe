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
  "@framework/ui/*": ["../../frappe/ui/src/*"]
}
```

The `paths` key must match the package name `@framework/ui` (also the key under
`dependencies`) so the specifier resolves the same way in TypeScript and the bundler.

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
