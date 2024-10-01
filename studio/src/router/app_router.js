import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/:appRoute/:pageRoute(.*)*",
		name: "AppContainer",
		component: () => import("@/pages/AppContainer.vue"),
		props: true,
	},
]

let router = createRouter({
	history: createWebHistory("/studio-app"),
	routes,
})

export default router
