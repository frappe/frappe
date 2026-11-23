import {
	createRouter,
	createWebHistory,
	type RouteRecordRaw,
	type Router,
	type RouterOptions,
} from "vue-router"
import { toast } from "frappe-ui"
import AppPage from "@/pages/AppPage.vue"
import { loadPage, discardPage } from "@/page/pageLoader"
import NotFound from "@/pages/NotFound.vue"

export type RouterConfig = {
	routerOptions?: Omit<RouterOptions, "history" | "routes">
	extendRoute?: (route: RouteRecordRaw) => void
	setup?: (router: Router) => void | Promise<void>
}

const CONFIG_KEYS = ["routerOptions", "extendRoute", "setup"]

interface Page {
	name: string
	route: string
	page_title: string
}

export type RendererApp = {
	name: string
	route: string
	pages: Page[]
	home?: string | null
	isGuest?: boolean
}

declare global {
	interface Window {
		app_name: string
		app_route: string
		app_pages: Page[]
		app_home?: string
		router_file?: string | null
		boot?: Record<string, unknown>
		is_guest?: boolean
	}
}

export function getWindowApp(): RendererApp {
	return {
		name: window.app_name,
		route: window.app_route,
		pages: window.app_pages,
		home: window.app_home,
		isGuest: window.is_guest,
	}
}

export async function createAppRouter(config: RouterConfig | undefined, app: RendererApp): Promise<Router> {
	config ??= await loadRouterConfig()
	const unknownKeys = Object.keys(config).filter((key) => !CONFIG_KEYS.includes(key))
	if (unknownKeys.length) {
		throw new Error(`router config: unknown keys ${unknownKeys.join(", ")}`)
	}
	const { routerOptions: options = {}, extendRoute } = config
	const routes = getPageRoutes(app)
	if (extendRoute) await runHook("extendRoute", () => routes.forEach((route) => extendPageRoute(route, extendRoute)))

	const router = createRouter({
		...options,
		history: createWebHistory(`/${app.route}`),
		routes,
	})
	await runHook("setup", () => config.setup?.(router))
	addHomeRouteFallback(router, app)
	addNotFoundRouteFallback(router, app)
	router.beforeEach((to) => sendGuestToLogin(to, app))
	router.beforeResolve((to, from) => loadPage(router, to, from))
	router.afterEach((to, _from, failure) => discardPage(to, failure))
	router.onError(reportNavigationError)
	return router
}

// Repository previews load the router file from the dev server. Database apps pass a browser-compiled
// config to createAppRouter; app builds import the config in their generated entry.
async function loadRouterConfig(): Promise<RouterConfig> {
	if (!window.router_file) return {}
	const mod = await runHook("router file", () => import(/* @vite-ignore */ window.router_file!))
	return mod.default || {}
}

function getPageRoutes(app: RendererApp): RouteRecordRaw[] {
	return (app.pages || []).map((page) => ({
		path: page.route,
		name: page.page_title,
		component: AppPage,
		props: true,
		meta: {
			pageName: page.name,
			appName: app.name,
			appRoute: app.route,
		},
	}))
}

// `route.meta = {...}` must not drop the page's own meta keys
function extendPageRoute(route: RouteRecordRaw, extendRoute: (route: RouteRecordRaw) => void) {
	const pageMeta = route.meta
	extendRoute(route)
	route.meta = { ...route.meta, ...pageMeta }
}

function addHomeRouteFallback(router: Router, app: RendererApp) {
	if (router.getRoutes().some((route) => route.path === "/")) return
	const home = router.getRoutes().find((route) => !route.aliasOf && route.meta.pageName === app.home)
	if (!home || home.path.includes(":")) return
	router.addRoute({ path: "/", component: AppPage, beforeEnter: () => home.path })
}

function addNotFoundRouteFallback(router: Router, app: RendererApp) {
	if (router.getRoutes().some((route) => route.path.includes("(.*)"))) return
	router.addRoute({
		path: "/:pathMatch(.*)*",
		name: "Not Found",
		component: NotFound,
		props: { home: `/${app.route}/` },
		meta: { notFound: true },
	})
}

function reportNavigationError(error: Error) {
	console.error(error)
	toast.error("Could not load page", { description: error.message })
}

// private routes are absent from a guest's page list, so an unknown path may exist after login
function sendGuestToLogin(to: { meta: { notFound?: boolean }; fullPath: string }, app: RendererApp) {
	if (!app.isGuest || !to.meta.notFound) return true
	const redirectTo = encodeURIComponent(`/${app.route}${to.fullPath}`)
	window.location.href = `/login?redirect-to=${redirectTo}`
	return false
}

async function runHook<T>(where: string, run: () => T | Promise<T>): Promise<T> {
	try {
		return await run()
	} catch (error) {
		const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
		throw new Error(`${where}: ${message}`, { cause: error })
	}
}
