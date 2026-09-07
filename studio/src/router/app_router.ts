import { createRouter, createWebHistory, type RouteRecordRaw } from "vue-router"
import AppContainer from "@/pages/AppContainer.vue"
import { toast } from "frappe-ui"

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

function getPageRoutes(pages: Page[] = []): RouteRecordRaw[] {
	return pages.map((page) => ({
		path: page.route,
		name: page.page_title,
		component: AppContainer,
		props: true,
		meta: {
			pageName: page.name,
			appRoute: window.app_route,
		},
	}))
}

const router = createRouter({
	history: createWebHistory(`/${window.app_route}`),
	routes: getPageRoutes(window.app_pages),
})

router.beforeEach((to) => {
	if (to.matched.length) return true

	if (window.is_guest) {
		// Private routes are absent for guests; retry after login.
		const redirectTo = encodeURIComponent(`/${window.app_route}${to.fullPath}`)
		window.location.href = `/login?redirect-to=${redirectTo}`
		return false
	}
	toast.error(`Failed to navigate to ${to.fullPath}`, {
		description: "Page does not exist or is not published",
	})
	return false
})

export default router
