# An app bundles its own island

An island is one ES module. It carries its own Vue, its own frappe-ui and every other package it imports. The host resolves the module's URL and imports it. The page publishes nothing for the island to link against, so the page needs nothing loaded before the island.

## Decision

Ownership follows the code. The app writes the island, so the app builds it, weighs it and ships it. Framework owns one seam: a name, a URL and the `mount(el, context)` export.

The seam is small enough to state in full. The host reads the island's bundle name from the `ui_islands` hook. It reads `<name>.island.js` and `<name>.island.css` from assets.json. It imports the module and calls `mount` with the host context and the stylesheet URL. Nothing else crosses.

The cost is duplication. Two islands from two apps on one page carry two copies of Vue. Each copy is a few hundred kB. Each copy is correct on its own, because two Vue apps in two shadow roots share no state.

## Rejected: a shared runtime the page publishes through an import map

Framework builds one copy of Vue, frappe-ui and everything under them. It writes an import map into the desk page. The app's build leaves those specifiers bare, and the page holds one copy of each.

This removes the duplication and costs three things.

**An ordering dependency between repos.** No app can build until framework builds. Every island on the site waits for a rebuild after each framework release.

**A registration that decides what an island bundles.** The map shares a specifier it carries. The build bundles a specifier the map misses, with everything behind it, and reports nothing. One registration missed `frappe-ui/charts`, and the island bundled 762 kB of echarts. Only the size budget objected.

**Framework depends on frappe-ui.** To build the runtime, framework resolves frappe-ui's entry points, walks its import graph, reconciles versions across the tree, and holds a patch for a package it never imports. Desk uses none of it.

An island that asks the page for Vue is an island the page can break. An island that bundles its own Vue breaks only on its own build.

## Rejected: desk exposes Vue as a global

`window.Vue`, the way desk exposes jQuery. It shares one copy without an import map and without a build step in framework.

It shares exactly one package. frappe-ui is 90% of an island's weight, and it cannot travel this way. Its components are source that the app's Tailwind compiles. So the island still bundles nearly everything, and desk gains a global it must keep forever.
