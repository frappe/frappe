import { createMemoryHistory, createRouter, createWebHistory } from "vue-router";

import { PAGES } from "./pages/pages.js";

// One page; the route names the open conversation, or the records shown in its place (a list,
// a record, or "new" for a blank one), so links and reloads keep it.
const kinds = PAGES.map((page) => page.key).join("|");
export const router = createRouter({
	history: window.top === window ? createWebHistory("/flow") : framedHistory("/flow"),
	routes: [
		{ path: "/", name: "new", component: { render: () => null } },
		{ path: "/s/:session", name: "session", component: { render: () => null } },
		{ path: `/:kind(${kinds})/:record?`, name: "records", component: { render: () => null } },
		{ path: "/:rest(.*)", redirect: "/" },
	],
});

// In a frame (the launcher's panel), Back and Forward are the page's; the address still follows
export function framedHistory(base) {
	const memory = createMemoryHistory(base);
	const backs = [null]; // the step before each, a record's way back to its list
	let at = 0;
	const { push, replace, go } = memory;
	const follow = () =>
		window.history.replaceState(window.history.state, "", base + memory.location);
	Object.assign(memory, {
		push(to, data) {
			backs.splice(++at, backs.length, memory.location);
			push(to, data);
			follow();
		},
		replace(to, data) {
			replace(to, data);
			follow();
		},
		go(delta, trigger) {
			at = Math.max(0, Math.min(at + delta, backs.length - 1));
			go.call(memory, delta, trigger);
			follow();
		},
	});
	Object.defineProperty(memory, "state", { get: () => ({ back: backs[at] }) });
	replace((location.pathname.slice(base.length) || "/") + location.search);
	return memory;
}
