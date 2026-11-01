import { mountVueIsland } from "@framework/ui/island";
import { frappeRequest, setConfig } from "frappe-ui";

import App from "./App.vue";
import { setPanel } from "./panel.js";
import { routes } from "./router.js";
import "./index.css";

// frappe-ui's list and document resources fetch through this
setConfig("resourceFetcher", frappeRequest);

// props: `panel` ("desk" or "app", the page around the launcher's panel; none on /flow),
// `boot` (rendered by /flow; the panel asks for it), `path` (the route to open), and the
// listeners onClose, onSettings(open), onNavigate(path)
export function mount(el, context) {
	setPanel(context.props?.panel);
	return mountVueIsland(el, {
		...context,
		component: App,
		routes,
		configure(app) {
			const router = app.config.globalProperties.$router;
			router.replace(context.props?.path || "/");
			router.afterEach((to) => context.props?.onNavigate?.(to.fullPath));
		},
	});
}
