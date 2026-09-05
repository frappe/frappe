// A second entry, so the build has something to share. It reaches the same
// helper and the same frappe-ui components as `panel.js`, which is what rollup
// lifts into a chunk both entries import.
import { mountVueIsland } from "@framework/ui/island";

import Badge from "./Badge.vue";

export function mount(el, context) {
	return mountVueIsland(el, { ...context, component: Badge });
}
