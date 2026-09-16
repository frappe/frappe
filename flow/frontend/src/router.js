import { createRouter, createWebHistory } from "vue-router";

// One page; the route only names the open conversation so links and reloads keep it.
export const router = createRouter({
	history: createWebHistory("/flow"),
	routes: [
		{ path: "/", name: "new", component: { render: () => null } },
		{ path: "/s/:session", name: "session", component: { render: () => null } },
		{ path: "/:rest(.*)", redirect: "/" },
	],
});
