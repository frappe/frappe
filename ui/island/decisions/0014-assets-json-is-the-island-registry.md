# assets.json is the island registry

An island is code an app exposes: a name, and props that select the content. `insights.dashboard` draws any dashboard. A **host** is anything that names an island and passes props — a desk `Page`, a workspace block, a form, or `<Island>` in another app's frontend. An island cannot rely on its host, so it works when the host ignores `title` and `actions`, and it takes its content from props, never from a desk route.

That model has one name for two registrations: the `ui_islands` hook named the island, and the build's asset key named the bundle. The hook was a rename between them.

## Decision

The build registers the island. An island's name is its asset key without `.island.js`, and the `ui_islands` hook goes. This amends [0001](0001-an-app-bundles-its-own-island.md), whose seam read the bundle name from the hook.

`get_ui_islands()` keeps the `.island.js` keys whose app is installed on the site. The app comes from the URL, `/assets/<app>/dist/...`. Filtering is the one job the hook did that nothing else does, because assets.json is bench-wide and a site holds a subset of the bench's apps.

Filtering is not a gate. An island's bundle is a public static file, and what it draws is protected by the app's own API. The hook never gated anything either.

Two builds writing one key is an error `writeIslandAssets` reports, because two islands claiming one name is two hosts drawing the wrong thing, and whichever built last would win silently.

The cost is that a name is now a Vite entry name. A rename breaks every host that names it, including the workspace files of apps that never build.

## Rejected: the hook stays

Keep `ui_islands` as the registry.

It keeps a rename nobody asked for. Every island is then two lines in two files that must agree, and the failure when they do not is a blank page. The hook's only real job, the installed-app filter, is a property of the URL the build already wrote.
