import { createRouter, createWebHistory } from "vue-router"

const routes = [
	{
		path: "/:pageRoute(.*)*",
		name: "AppContainer",
		component: () => import("@/pages/AppContainer.vue"),
		props: true,
	},
]

interface Page {
	name: string
	route: string
	page_title: string
}
declare global {
	interface Window {
		app_name: string
		app_route: string
		app_pages: Page[]
	}
}

let router = createRouter({
	history: createWebHistory(`/${window.app_route}`),
	routes,
})

const addDynamicRoutes = (appRoute: string, pages: Page[]) => {
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

router.beforeEach((to, _, next) => {
	if (to.params.pageRoute && to.params.pageRoute !== "studio") {
		// if pageRoute is still a param, dynamic routes have not been added yet
		try {
			addDynamicRoutes(to.params.appRoute as string, window.app_pages)
			// Redirect to the same route to trigger re-evaluation with new routes
			return next(to.fullPath)
		} catch (error) {
			console.error("Error adding dynamic routes:", error)
			return next()
		}
	}
	next()
})

export default router
