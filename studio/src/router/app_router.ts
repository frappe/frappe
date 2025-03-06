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
		app_route: string
		app_pages: Page[]
	}
}

let router = createRouter({
	history: createWebHistory(`/${window.app_route}`),
	routes,
})

const addDynamicRoutes = (appRoute: string) => {
	const pages = window.app_pages

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
	addDynamicRoutes(window.app_route)
	next()
})

export default router
