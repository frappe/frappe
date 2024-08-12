import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/page",
		name: "StudioPage",
		component: () => import("@/pages/StudioPage.vue"),
	},
]

let router = createRouter({
	history: createWebHistory("/studio"),
	routes,
})

export default router
