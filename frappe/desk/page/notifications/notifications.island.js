import { mountVueIsland } from "@framework/ui/island";

import Page from "./notifications.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
