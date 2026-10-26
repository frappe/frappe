import { mountVueIsland } from "@framework/ui/island";

import Page from "./workspace_view.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
