import { createRouter, createWebHistory } from "vue-router"
import { fetchAppPages } from "@/utils/helpers"

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

const addDynamicRoutes = async (appRoute: string) => {
	const pages = await fetchAppPages(appRoute)

	pages.forEach((page) => {
		router.addRoute({
			path: page.route.replace("studio-app", ""),
			name: page.page_title,
			component: () => import("@/pages/AppContainer.vue"),
			props: true,
			meta: {
				isDynamic: true,
				appRoute: appRoute,
			},
		})
	})
}

router.beforeEach(async (to, _, next) => {
	// TODO: find a performant way to handle adding dynamic routes
	if (to.params.appRoute && to.params.appRoute !== "studio") {
		try {
			await addDynamicRoutes(to.params.appRoute as string)

			// Redirect to the same route to trigger re-evaluation with new routes
			return next(to.fullPath)
		} catch (error) {
			console.error("Error fetching dynamic routes:", error)
			return next()
		}
	}

	next()
})

export default router
