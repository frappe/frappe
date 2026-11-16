import { createWebHistory } from "vue-router";
import { mountVueIsland } from "@framework/ui/island";
import { frappeRequest, setConfig } from "frappe-ui";

import App from "./App.vue";
import { loadBoot } from "./boot.js";
import { setAskedSession, setPanel } from "./panel.js";
import { routes } from "./router.js";
import "./index.css";

// frappe-ui's list and document resources fetch through this
setConfig("resourceFetcher", frappeRequest);

// frappe-ui's Spinner turns a custom property its CSS registers with @property, which a shadow
// root ignores; registered for the page instead, it spins. Already registered: nothing to do
try {
	CSS.registerProperty({ name: "--fui-spinner-angle", syntax: "<angle>", inherits: false, initialValue: "0deg" });
} catch {}

// props: `panel` ("desk" or "app", the page around the launcher's panel; none on /flow),
// `boot` (rendered by /flow; the panel asks for it), `path` (the route the panel opens), `asked`
// (the chat an app asked for, when that is the route), and
// the listeners onClose, onNavigate(path). On /flow the routes are the
// address after /flow; in the panel they run on a memory history and the launcher keeps the
// last one for the next page. A new `path` moves an open panel to that route.
export async function mount(el, context) {
	const panel = context.props?.panel;
	setPanel(panel);
	setAskedSession(context.props?.asked);
	// the launcher's skeleton shows until the mount resolves, so the panel loads boot first and
	// the chat draws at once; a failed load leaves App to try again and say why
	const boot = panel ? await loadBoot().catch(() => null) : context.props?.boot;
	let router;
	const island = await mountVueIsland(el, {
		...context,
		props: { ...context.props, boot },
		component: App,
		routes,
		history: panel ? null : createWebHistory("/flow"),
		configure(app) {
			if (!panel) return;
			router = app.config.globalProperties.$router;
			router.replace(context.props.path || "/");
			router.afterEach((to) => context.props.onNavigate?.(to.fullPath));
		},
	});
	island.shadow_root.host.toggleAttribute("data-panel", Boolean(panel));
	if (!panel) return island;
	const update = island.update;
	return {
		...island,
		update(next) {
			update(next);
			if (next.asked) setAskedSession(next.asked);
			if (next.path && next.path !== router.currentRoute.value.fullPath) router.replace(next.path);
		},
	};
}
