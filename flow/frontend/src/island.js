import { createWebHistory } from "vue-router";
import { mountVueIsland } from "@framework/ui/island";
import { frappeRequest, setConfig } from "frappe-ui";

import App from "./App.vue";
import { setPanel } from "./panel.js";
import { routes } from "./router.js";
import "./index.css";

// frappe-ui's list and document resources fetch through this
setConfig("resourceFetcher", frappeRequest);

// props: `panel` ("desk" or "app", the page around the launcher's panel; none on /flow),
// `boot` (rendered by /flow; the panel asks for it), `path` (the route the panel opens), and
// the listeners onClose, onSettings(open), onNavigate(path). On /flow the routes are the
// address after /flow; in the panel they run on a memory history and the launcher keeps the
// last one for the next page.
export async function mount(el, context) {
	const panel = context.props?.panel;
	setPanel(panel);
	const island = await mountVueIsland(el, {
		...context,
		component: App,
		routes,
		history: panel ? null : createWebHistory("/flow"),
		configure(app) {
			if (!panel) return;
			const router = app.config.globalProperties.$router;
			router.replace(context.props.path || "/");
			router.afterEach((to) => context.props.onNavigate?.(to.fullPath));
		},
	});
	island.shadow_root.host.toggleAttribute("data-panel", Boolean(panel));
	return island;
}
