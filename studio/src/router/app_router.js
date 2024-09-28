import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/:appRoute/:pageRoute",
		name: "AppContainer",
		component: () => import("@/pages/AppContainer.vue"),
	},
]

let router = createRouter({
	history: createWebHistory("/studio-app"),
	routes,
})

export default router
