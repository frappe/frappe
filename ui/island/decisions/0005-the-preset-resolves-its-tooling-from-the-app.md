# The preset resolves its tooling from the app

The preset needs vite, `@vitejs/plugin-vue`, Tailwind, autoprefixer, TypeScript
and frappe-ui's icon resolver to run a build. It loads each one out of the app it
is building.

## Decision

`loadTools(root)` writes a module into the app's `node_modules/.island/` that
re-exports every build-time dependency by name, and imports that file.

Node resolves a bare specifier from the importing module's real path. A bench
links `@framework/ui` by relative path, so an `import "vite"` inside the preset
would look beside the framework checkout — a tree a bench never installs a
frontend's dependencies into. A file written into the app's own tree resolves
against the app's dependencies instead, and the generated Tailwind config sits
there for the same reason.

This also settles which versions an island is built with. The app's lockfile
decides, the same lockfile its SPA build answers to, so an island and the app's
own pages compile the same frappe-ui the same way.

A specifier that does not resolve fails the build with the app's root named and
`devDependencies` as the fix. `@framework/ui` declares all of them as optional
peer dependencies, so a consuming app is told once, at install.

## Rejected: resolve each specifier by hand

`require.resolve` from a require rooted at the app, or `import.meta.resolve`
with the app as the parent.

`require.resolve` reads the `require` condition, so it refuses an ESM-only
subpath — `frappe-ui/vite/lucideIconsPlugin` among them.
`import.meta.resolve` ignores its parent argument unless node runs with
`--experimental-import-meta-resolve`, and answers for the preset's own path
instead, silently. Writing the file hands the whole job to node's resolver.

## Rejected: framework declares the tooling

Put vite, Tailwind and the rest in `apps/frappe/package.json`, where the preset's
own path resolves them.

Framework then installs a second frontend toolchain it never runs, and pins the
versions every app's islands are built with. An app on a newer vite would build
its SPA with one and its islands with another.

## Rejected: the app passes the modules in

`buildIslands({ vite, tailwindcss, ... })`.

It is the same resolution, written out by every app, and an app that passes the
wrong thing finds out inside rollup.
