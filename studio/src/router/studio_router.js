import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/home",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/app/:appID",
		name: "StudioApp",
		component: () => import("@/pages/StudioApp.vue"),
	},
	{
		path: "/app/:appID/:pageID",
		name: "StudioPage",
		component: () => import("@/pages/StudioPage.vue"),
	},
]

let router = createRouter({
	history: createWebHistory("/studio"),
	routes,
})

export default router
