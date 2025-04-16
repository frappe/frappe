import { createRouter, createWebHistory } from "vue-router"
import session from "@/utils/session"

const routes = [
	{
		path: "/home",
		name: "Home",
		component: () => import("@/pages/Home.vue"),
	},
	{
		path: "/",
		redirect: "home",
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


router.beforeEach(async (to, _, next) => {
	!session.initialized && (await session.initialize())

	if (!session.isLoggedIn) {
		window.location.href = "/login?redirect-to=/studio"
		return next(false)
	}
	return next()
})

export default router
