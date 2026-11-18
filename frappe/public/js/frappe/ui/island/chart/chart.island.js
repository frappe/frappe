import { mountVueIsland } from "@framework/ui/island";

import Chart from "./chart.vue";

export const mount = (el, context) => mountVueIsland(el, { ...context, component: Chart });
