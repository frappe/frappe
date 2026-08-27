# The mount contract lives with frappe-ui, not in desk

`mountVueIsland` is what turns a Vue component into an island: it opens the
shadow root, adopts the stylesheets, mirrors the host's theme, gives frappe-ui's
overlays a portal target inside the root, and returns the `update`/`unmount`
handle desk holds. It ships in `@framework/ui`, and the app's build compiles it
into the island.

## Decision

The contract lives on the frappe-ui side of the boundary, next to the components
it exists to host.

Every line of it is about Vue and frappe-ui. It calls `createApp`, it provides
`portalTargetKey`, it installs a memory router because frappe-ui components call
`useRouter()` unconditionally. Code that reasons about frappe-ui belongs where
frappe-ui is a dependency.

Desk's half is the other side of the same seam and stays in desk:
`frappe.ui.mount_island` resolves the name, assembles the desk context, and calls
the island's `mount`. It touches no Vue, so desk's bundle stays what it is.

`@framework/ui/island` also exports `deskKey` and `useDesk`, so an island reads
its host context through the same module that provides it, rather than each app
declaring the symbol again.

## Rejected: desk ships the mount contract

Desk's bundle exposes `frappe.ui.mount_vue_island`, and an island calls it off
`window`.

Desk would need Vue, vue-router and frappe-ui in its own dependencies to compile
it, and every island on the page would run against desk's copies — which is the
shared runtime, arrived at sideways
([0001](0001-an-app-bundles-its-own-island.md)). It also makes the contract
invisible to an app's type checker and its bundler.

## Rejected: every app writes its own

A shadow root and a `createApp` are twenty lines, so each app could open its own.

The details are not twenty lines. The portal target, the stacking tier over
desk's chrome, the theme attribute inside the root, the compiler's comment
handling — each was found once and each is silent when wrong. One
implementation is the only way the second app gets them for free.
