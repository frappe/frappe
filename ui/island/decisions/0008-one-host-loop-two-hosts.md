# One host loop, two hosts

Desk was the first host of an island. A frappe-ui app — CRM, Insights — is the
second. The loop between a name and a mounted island is the same for both:
resolve the name, import the module, check it exports `mount`, tear down what
holds the target, call `mount`, and keep a handle that survives a re-mount.

## Decision

That loop lives once, in `ui/island/host.js`, and each host is a thin wrapper
over it.

The loop imports nothing — not vue, not frappe-ui, not frappe. What differs
between hosts is injected: a `resolve(name)` that returns the module and
stylesheet URLs, and the context the island reads through `useDesk()`. Desk
resolves against `frappe.boot`, `<Island>` calls
`frappe.utils.island.get_island_assets`.

Desk keeps what is desk's: the boot registry, the desk context, the
`frappe.ui.mount_island` API and the hot-update registration. `<Island>` keeps
what is Vue's: the lifecycle, the prop watch, and the token that unmounts an
island whose load finished after the component was gone.

The rules the loop carries are the ones that were each found once and are silent
when wrong. A re-mount keeps the handle the caller holds. A module that fails to
load leaves the island already on screen alone. The context key is `desk`.

## Rejected: two loaders, each with its own loop

Two hundred lines, twice. The second copy starts correct and drifts: the hot
re-mount fix landed in desk's loop after the loop was written, and the
Vue host would not have it.

## Rejected: desk exposes the loop on `window`

`frappe.ui.mount_island` is already global on a desk page, so `<Island>` could
call it.

It only works on a desk page. A frappe-ui app is its own SPA, served from its own
route, with no desk bundle on it. It would also make the Vue host depend on
desk's resolution — the boot registry — where it has an API instead.

## Rejected: `<Island>` calls `frappe.ui.mount_island`

The same coupling with an extra step: the component would carry a fallback for
when the global is absent, which is every page it actually runs on.
