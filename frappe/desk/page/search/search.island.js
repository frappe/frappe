// The island entry for this page. Desk imports this module and calls `mount`.
//
// `mountVueIsland` opens the shadow root, adopts this app's stylesheet, mirrors
// desk's theme and gives frappe-ui's overlays a portal target inside the root.
import { mountVueIsland } from "@framework/ui/island";

import Page from "./search.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
