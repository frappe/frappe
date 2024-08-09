import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
]

let router = createRouter({
	history: createWebHistory("/studio"),
	routes,
})

export default router
