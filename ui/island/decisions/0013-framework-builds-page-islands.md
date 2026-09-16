# Framework builds page islands

An island builds on the app's own tooling ([0005](0005-the-preset-resolves-its-tooling-from-the-app.md)). A page island cannot. Most apps that ship desk pages have no frontend at all, and framework itself has none. Under that rule the first step of a starter is "set up Vite", which is the whole barrier and has nothing to do with islands.

## Decision

One build, run by framework, for every Frappe UI page on the bench. Its vite root is `ui/vite/island/toolchain/`, a directory whose only content is the build's own dependencies.

This amends 0005 rather than reversing it. The preset still resolves its tooling from its root. For this one build that root is framework's, and an app's own islands are untouched.

So a page island compiles against framework's frappe-ui, `@framework/ui`, and nothing of the app's. That is the shape of a starter and not a limitation to work around: a page that needs the app's own components has outgrown the scaffold, and it moves into the app's frontend as an ordinary island.

One build and not one per app, for the reason in [0002](0002-an-app-builds-its-islands-together.md) and again for [0003](0003-tailwind-scans-the-module-list-not-a-glob.md): every page island on the bench shares one vue chunk and one frappe-ui chunk, and the scan's throwaway first pass runs once instead of once per app. `after_app_build` runs it, because any app's build can be the one that added a page.

Output is `sites/assets/frappe/dist/page-island/`, not `dist/island/`. A build owns every assets.json key pointing into its own directory, so framework's build and an app's own build need two directories or they drop each other's keys.

Discovery reads each page's json for its name and its type, rather than reading the folder. The folder is the scrubbed name, and scrubbing is not reversible: `sales_dashboard` could be either `sales-dashboard` or `sales_dashboard`, and the name the build picks has to be the one `page_island_name` picks in Python.

## Rejected: the app builds its own page islands

The rule 0005 already sets, applied to pages.

It works only for an app that already has a frontend, which is the minority and never framework. The setup it asks for is a `package.json`, a lockfile, a build script and an `after_build` hook, all before the first page renders. The app's build stays the graduation path, which is where an island that needs the app's own code belongs anyway.

## Rejected: install the toolchain at `ui/`

The simpler-looking version of the same idea: put the dependencies in `@framework/ui` itself and root the build there.

A bench links `@framework/ui` into every consuming app by symlink, and node resolves from a module's real path. A `vue` and a `frappe-ui` sitting in `ui/node_modules` are a second copy for every app that links the package. The README calls that out as the thing that breaks provide/inject and doubles vue. A sibling directory is never on the walk up from `ui/src`.

## Rejected: framework hosts a frontend of its own

Give `apps/frappe` a real frontend and let page islands build there.

That frontend is being introduced for the desk work already. Standing up a second one now means merging or deleting one later, and it carries an SPA's worth of configuration for a build that needs six packages.
