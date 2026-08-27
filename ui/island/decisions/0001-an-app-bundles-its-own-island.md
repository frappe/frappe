# An app bundles its own island

An island is one ES module. It carries its own Vue, its own frappe-ui and every
other package it imports. Desk resolves the module's URL and imports it. The page
publishes nothing for the island to link against, so nothing has to be on the
page before the island loads.

## Decision

Ownership follows the code. The app writes the island, so the app builds it,
weighs it and ships it. Framework owns one seam: a name, a URL and the
`mount(el, context)` export at the end of it.

That seam is small enough to state in full. `frappe.ui.mount_island` reads the
`ui_islands` hook for the island's bundle name, reads `<name>.island.js` and
`<name>.island.css` out of assets.json, imports the module, and calls `mount`
with the desk context and the stylesheet URL. Nothing else crosses.

The cost is duplication. Two islands from two apps on one page carry two copies
of Vue. Each copy is a few hundred kB, and each is correct on its own — two Vue
apps in two shadow roots share no state and need none.

## Rejected: a shared runtime the page publishes through an import map

Framework builds one copy of Vue, frappe-ui and everything under them, writes an
import map into the desk page, and the app's build leaves those specifiers bare.
The page then holds one copy of each.

It buys the duplication back and charges three things for it.

**An ordering dependency between repos.** No app can build until framework has
built, and every island on the site is a rebuild behind whatever framework
publishes.

**A registration that decides what an island bundles.** A specifier the map
carries is shared, and a specifier it misses is bundled silently, with everything
behind it. `frappe-ui/charts` missing from a registration cost one island 762 kB
of echarts, and only a size budget objected.

**Framework depending on frappe-ui.** Building the runtime means resolving
frappe-ui's entry points, walking its import graph, reconciling versions across
the tree, and holding a patch for a package it never imports itself. Desk uses
none of it.

An island that has to ask the page for Vue is an island the page can break. This
one cannot be broken by anything but its own build.

## Rejected: desk exposes Vue as a global

`window.Vue`, the way desk exposes jQuery. It shares one copy without an import
map and without a build step in framework.

It shares exactly one package. frappe-ui is 90% of an island's weight and cannot
travel this way, because its components are source that has to be compiled
against the app's Tailwind. So the island still bundles nearly everything, and
desk gains a global it must keep working forever.
