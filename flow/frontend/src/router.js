import { createRouter, createWebHistory } from "vue-router";

import { PAGES } from "./pages/pages.js";

// One page; the route names the open conversation, or the records shown in its place (a list,
// a record, or "new" for a blank one), so links and reloads keep it.
const kinds = PAGES.map((page) => page.key).join("|");
export const router = createRouter({
	history: createWebHistory("/flow"),
	routes: [
		{ path: "/", name: "new", component: { render: () => null } },
		{ path: "/s/:session", name: "session", component: { render: () => null } },
		{ path: `/:kind(${kinds})/:record?`, name: "records", component: { render: () => null } },
		{ path: "/:rest(.*)", redirect: "/" },
	],
});
