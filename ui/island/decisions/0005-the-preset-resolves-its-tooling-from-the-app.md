# The preset resolves its tooling from the app

The preset needs Vite, `@vitejs/plugin-vue`, Tailwind, autoprefixer, TypeScript and frappe-ui's icon resolver to run a build. It loads each one from the app it builds.

## Decision

`loadTools(root)` writes a module into the app's `node_modules/.island/`. The module re-exports every build-time dependency by name, and the preset imports it.

Node resolves a bare specifier from the importing module's real path. A bench links `@framework/ui` by relative path, so an `import "vite"` inside the preset would look beside the framework checkout. A bench never installs a frontend's dependencies there. A file written into the app's own tree resolves against the app's dependencies. The generated Tailwind config sits there for the same reason.

This also settles which versions build an island. The app's lockfile decides. The same lockfile builds the app's SPA, so an island and the app's own pages compile the same frappe-ui the same way.

A specifier that does not resolve fails the build. The error names the app's root and `devDependencies` as the fix. `@framework/ui` declares all of them as optional peer dependencies, so a consuming app is told once, at install.

## Rejected: resolve each specifier by hand

`require.resolve` from a require rooted at the app, or `import.meta.resolve` with the app as the parent.

`require.resolve` reads the `require` condition, so it refuses an ESM-only subpath. `frappe-ui/vite/lucideIconsPlugin` is one. `import.meta.resolve` ignores its parent argument unless Node runs with `--experimental-import-meta-resolve`. It then answers for the preset's own path and reports nothing. The written file hands the whole job to Node's resolver.

## Rejected: framework declares the tooling

Put Vite, Tailwind and the rest in `apps/frappe/package.json`, where the preset's own path resolves them.

Framework then installs a second frontend toolchain it never runs, and pins the versions every app's islands build with. An app on a newer Vite builds its SPA with one version and its islands with another.

## Rejected: the app passes the modules in

`buildIslands({ vite, tailwindcss, ... })`.

It is the same resolution, written out by every app. An app that passes the wrong module finds out inside Rollup.
