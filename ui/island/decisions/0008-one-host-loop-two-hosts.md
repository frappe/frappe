# One host loop, two hosts

Desk was the first host of an island. A frappe-ui app, such as CRM or Insights, is the second. The loop between a name and a mounted island is the same for both. Resolve the name. Import the module. Check that it exports `mount`. Unmount what holds the target. Call `mount`. Keep a handle that survives a re-mount.

## Decision

That loop lives once, in `ui/island/host.js`. Each host is a thin wrapper over it.

The loop imports nothing: not Vue, not frappe-ui, not frappe. Each host injects what differs: a `resolve(name)` that returns the module and stylesheet URLs, and the context the island reads through `useHost()`. The desk loader resolves against `frappe.boot`. `<Island>` calls `frappe.utils.island.get_island_assets`.

Desk keeps what is desk's: the boot registry, the desk context, the `frappe.ui.mount_island` API and the hot-update registration. `<Island>` keeps what is Vue's: the lifecycle and the prop watch.

The handle is synchronous, so the loop owns the load as well as the mount. A caller holds the handle from the first line. `update` and `unmount` work before the module loads. Before this, every host carried the same guard against an import that finished after the caller moved on. Three did.

The loop carries the rules that were each found once and that fail without a report when wrong. A re-mount keeps the handle the caller holds. A module that fails to load leaves the island already on screen alone. The context key is `host`, not `desk`. Inside an island that CRM hosts, the context is CRM's.

## Rejected: two loaders, each with its own loop

The loop is two hundred lines, and two loaders hold it twice. The second copy starts correct and then drifts. The hot re-mount fix landed in desk's loop after the Vue host was written, and the Vue host would not have it.

## Rejected: desk exposes the loop on `window`

`frappe.ui.mount_island` is already global on a desk page, so `<Island>` could call it.

It works only on a desk page. A frappe-ui app is its own SPA, served from its own route, with no desk bundle on it. It would also tie the Vue host to desk's resolution, the boot registry, where it has an API instead.

## Rejected: `<Island>` calls `frappe.ui.mount_island`

The same coupling with an extra step. The component would carry a fallback for when the global is absent, which is every page it runs on.
