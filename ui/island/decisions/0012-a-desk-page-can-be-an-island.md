# A desk page can be an island

A desk page is a `.js` file with `on_page_load`. An app that wanted a Vue screen at a desk route wrote that file, built an island in its own frontend, declared it in `hooks.py`, and then repeated the mount, the chrome and the unmount by hand. `dashboard-view` is that page written once. It is sixty lines before it draws anything, and every one of its rules fails without a report when wrong.

## Decision

`Page` grows a `type`. When it is "Frappe UI", an island draws the page.

`pageview.js` builds the page, mounts the island, hands it the route below the page, and sets the head from what the island reports ([0010](0010-a-page-island-reports-title-and-actions.md)). The page ships no script. `load_assets` does not read one, so none reaches the client, where an island's entry would be eval'd as a classic script and fail.

The page registers its own island. `get_ui_islands` reads Page rows beside the `ui_islands` hook, so a page island needs no hook and no line of Python. The name is `<app>.page.<page name>`, derived the same way on both sides, and the `page` infix keeps it clear of the names an app declares by hand.

The starter is two files beside the page's json, `<page>.island.js` and `<page>.vue`, written once by `on_update` in place of the page script every other type gets.

Blank is the other type, and every page that exists today is blank. Readers branch on "Frappe UI" alone, so nothing was migrated and no app's exported json moved.

## Rejected: a `Route Type`

The routing work has a `Route` table whose rows name a `Route Type`, and only a `Route Type` names code. An island-drawn route looks like one of those.

`Route` registers mounts. A desk page is content behind a mount desk already owns, so this is not the same question. The routing model is also still a set of decisions with no code behind it, and a starter cannot wait on it.

## Rejected: the scaffold mounts the island

`on_update` writes a `.js` that calls `frappe.ui.mount_island` with the title, the actions and the unmount spelled out, and `type` is only a flag that chose a template.

Every page then starts with a correct copy and drifts. The route-race guard `dashboard-view` needed was found after that page was written, and no scaffolded page would ever get it. It also makes `type` a record of how a page was once created rather than a fact about how it is drawn.

## Rejected: the page names its bundle in `hooks.py`

The registry an app writes by hand, with the page pointing at a bundle name.

Three places to keep in step for a page whose parts are all in one folder, and the one a starter would forget. Reading the rows adds a source to the registry, not a second way to resolve a name: the loader, `get_island_assets` and `<Island>` are unchanged.
