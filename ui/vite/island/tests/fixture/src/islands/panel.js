// Fixture island entry, written the way an app writes one.
import { mountVueIsland } from "@framework/ui/island";

import Panel from "./Panel.vue";
import "./panel.css";

export function mount(el, context) {
	return mountVueIsland(el, { ...context, component: Panel });
}
