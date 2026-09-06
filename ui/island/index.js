// The island client contract: what an app's island entry imports.
//
// The build side is `@framework/ui/vite/island`. The desk side is
// `frappe.ui.mount_island`, which resolves an island's name and calls the
// `mount` export this module's `mountVueIsland` returns a handle for.

export { mountVueIsland } from "./mount.js";
export { hostKey, useHost } from "./context.js";
