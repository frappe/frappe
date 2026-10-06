import { mountVueIsland } from "@framework/ui/island";

import Page from "./profile.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Page });
