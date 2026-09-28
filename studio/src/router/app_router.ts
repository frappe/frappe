import {
	createRouter,
	createWebHistory,
	type RouteRecordRaw,
	type Router,
	type RouterOptions,
} from "vue-router"
import AppContainer from "@/pages/AppContainer.vue"
import { toast } from "frappe-ui"

interface Page {
	name: string
	route: string
	page_title: string
}

// An app's studio/<app>/router.ts default export: a createRouter call with the two Studio-specific
// pieces pulled out. `history` is withheld, Studio fixes the base.
export type RouterConfig = Omit<RouterOptions, "history" | "routes"> & {
	// once per Studio page, with the plain vue-router record; mutate it
	extendRoute?: (route: RouteRecordRaw) => void
	// the live router, before app.use(router)
	setup?: (router: Router) => void | Promise<void>
}

declare global {
	interface Window {
		app_name: string
		app_route: string
		app_pages: Page[]
		app_home?: string
		app_router_file?: string | null
		boot?: Record<string, unknown>
		is_guest?: boolean
	}
}

export async function createAppRouter(config: RouterConfig = {}): Promise<Router> {
	const { extendRoute, setup, ...options } = config
	const routes = getPageRoutes(window.app_pages)
	if (extendRoute) routes.forEach((route) => extendRoute(route))
	const homeRedirect = getHomeRedirect(routes)
	if (homeRedirect) routes.push(homeRedirect)

	const router = createRouter({
		...options,
		history: createWebHistory(`/${window.app_route}`),
		routes,
	})
	await setup?.(router)
	// after the app's guards, so a catch-all the app added wins over this
	router.beforeEach(unmatchedRouteGuard)
	return router
}

// the dev preview imports router.ts from the vite dev server; the production build compiles it in
export async function loadRouterConfig(): Promise<RouterConfig> {
	if (!window.app_router_file) return {}
	const mod = await import(/* @vite-ignore */ window.app_router_file)
	return mod.default || {}
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

function getHomeRedirect(routes: RouteRecordRaw[]): RouteRecordRaw | undefined {
	if (routes.some((route) => route.path === "/")) return
	// absent from the list when unpublished or private for a guest, then "/" stays unmatched
	const home = routes.find((route) => route.meta?.pageName === window.app_home)
	if (!home || home.path.includes(":")) return
	return { path: "/", redirect: home.path }
}

function unmatchedRouteGuard(to: { matched: unknown[]; fullPath: string }) {
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
}
