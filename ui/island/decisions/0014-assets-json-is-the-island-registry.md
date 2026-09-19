# assets.json is the island registry

An island is code an app exposes: a name, and props that select the content. `insights.dashboard` draws any dashboard. A **placement** is any host that names an island and passes props — a desk `Page`, a workspace block, a form, or `<Island>` in another app's frontend. An island cannot rely on its host, so it works when the host ignores `title` and `actions`, and it takes its content from props, never from a desk route.

That model has one name for two registrations: the `ui_islands` hook named the island, and the build's asset key named the bundle. The hook was a rename between them.

## Decision

The build registers the island. An island's name is its asset key without `.island.js`, and the `ui_islands` hook goes. This amends [0001](0001-an-app-bundles-its-own-island.md), whose seam read the bundle name from the hook, and [0013](0013-framework-builds-page-islands.md), whose page islands registered from their `Page` rows.

`get_ui_islands()` keeps the `.island.js` keys whose app is installed on the site. The app comes from the URL, `/assets/<app>/dist/...`, and for a page island, which framework builds into framework's own dist, from its name `<app>.page.<page name>`. Filtering is the one job the hook did that nothing else does, because assets.json is bench-wide and a site holds a subset of the bench's apps.

Filtering is not a gate. An island's bundle is a public static file, and what it draws is protected by the app's own API. The hook never gated anything either.

Two builds writing one key is an error `writeIslandAssets` reports, because two islands claiming one name is two placements drawing the wrong thing, and whichever built last would win silently.

A `Page` of type "Frappe UI" names an island the app built, in an `island` field. Empty still means the island framework builds from the page's folder. So the app's own components reach a desk route, which 0013 said had "outgrown the scaffold", and the page keeps what the page type gives it: the mount, the unmount, the route race, `route` and `query` as props, and a head drawn from what the island reports. `Page.get_island_name` derives the name when the field is empty, `load_assets` hands it to desk, and no save stores it.

The cost is that a name is now a Vite entry name. A rename breaks every placement that names it, including the workspace files of apps that never build.

## Rejected: the hook stays, and a page names a hook entry

Keep `ui_islands` as the registry and have the `Page` field point into it.

It keeps a rename nobody asked for. Every island is then two lines in two files that must agree, and the failure when they do not is a blank page. The hook's only real job, the installed-app filter, is a property of the URL the build already wrote.

It also cannot reach the build. Page discovery is Node, in `vite/island/pages.js`, and it cannot read `hooks.py`. A page that names an app's island still has to tell that build to skip it, which is a fact the page's own json has to carry.

## Rejected: the page's component wraps `<Island>`

No framework change. The scaffolded `.vue` renders `<Island name="insights.dashboard">` and forwards `route` and `query`.

Two shadow roots, one inside the other, for one screen. The overlay portal target, the theme mirroring and the stylesheet adoption each run twice, and the outer island carries a second copy of Vue and frappe-ui for a component that renders one tag. It also keeps building a page bundle for a page whose content is elsewhere.
