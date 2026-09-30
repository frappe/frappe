import {
	createRouter,
	createWebHistory,
	type RouteRecordRaw,
	type Router,
	type RouterOptions,
} from "vue-router"
import AppContainer from "@/pages/AppContainer.vue"
import NotFound from "@/pages/NotFound.vue"

interface Page {
	name: string
	route: string
	page_title: string
}

// An app's studio/<app>/router.ts default export
export type RouterConfig = {
	// forwarded to createRouter; `routes` and `history` are withheld, Studio owns both
	options?: Omit<RouterOptions, "history" | "routes">
	// once per Studio page, with the plain vue-router record; mutate it
	extendRoute?: (route: RouteRecordRaw) => void
	// called once, awaited before app.use(router) and the first navigation
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
	const { options = {}, extendRoute, setup } = config
	for (const key of ["routes", "history"]) {
		if (key in options) console.warn(`router.ts: options.${key} is ignored, Studio owns it`)
	}
	const routes = getPageRoutes(window.app_pages)
	if (extendRoute) routes.forEach((route) => extendRoute(route))

	const router = createRouter({
		...options,
		history: createWebHistory(`/${window.app_route}`),
		routes,
	})
	await setup?.(router)
	addHomeRouteFallback(router)
	addNotFoundRouteFallback(router)
	router.beforeEach(sendGuestToLogin)
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

function addHomeRouteFallback(router: Router) {
	if (router.getRoutes().some((route) => route.path === "/")) return
	const home = router.getRoutes().find((route) => !route.aliasOf && route.meta.pageName === window.app_home)
	if (!home || home.path.includes(":")) return
	router.addRoute({ path: "/", component: AppContainer, beforeEnter: () => home.path })
}

function addNotFoundRouteFallback(router: Router) {
	if (router.getRoutes().some((route) => route.path.includes("(.*)"))) return
	router.addRoute({
		path: "/:pathMatch(.*)*",
		name: "Not Found",
		component: NotFound,
		props: { home: `/${window.app_route}/` },
		meta: { notFound: true },
	})
}

// private routes are absent from a guest's page list, so an unknown path may exist after login
function sendGuestToLogin(to: { meta: { notFound?: boolean }; fullPath: string }) {
	if (!window.is_guest || !to.meta.notFound) return true
	const redirectTo = encodeURIComponent(`/${window.app_route}${to.fullPath}`)
	window.location.href = `/login?redirect-to=${redirectTo}`
	return false
}
