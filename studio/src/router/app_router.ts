import { createRouter, createWebHistory } from "vue-router"
import AppContainer from "@/pages/AppContainer.vue"
import { toast } from "frappe-ui"

const routes = [
	{
		path: "/:pageRoute(.*)*",
		name: "AppContainer",
		component: AppContainer,
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
		is_guest?: boolean
	}
}

let router = createRouter({
	history: createWebHistory(`/${window.app_route}`),
	routes,
})

const addDynamicRoutes = (appRoute: string, pages: Page[]) => {
	router.removeRoute("AppContainer")
	pages.forEach((page) => {
		router.addRoute({
			path: page.route,
			name: page.page_title,
			component: AppContainer,
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
	if (!to.matched.length) {
		if (window.is_guest) {
			// Private routes are absent for guests; retry after login.
			const redirectTo = encodeURIComponent(`/${window.app_route}${to.fullPath}`)
			window.location.href = `/login?redirect-to=${redirectTo}`
			return false
		}
		toast.error(`Failed to navigate to ${to.fullPath}`, {
			description: "Page does not exist or is not published"
		})
		return false
	}
	next()
})

export default router
