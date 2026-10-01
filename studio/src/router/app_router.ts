import {
	createRouter,
	createWebHistory,
	type RouteRecordRaw,
	type Router,
	type RouterOptions,
} from "vue-router"
import { createApp } from "vue"
import AppContainer from "@/pages/AppContainer.vue"
import RouterError from "@/pages/RouterError.vue"
import NotFound from "@/pages/NotFound.vue"
import { vueReactivityApis } from "@/stores/codeStore"
import * as globalUtils from "@/utils/globalUtils"

interface Page {
	name: string
	route: string
	page_title: string
}

// An app's studio/<app>/router.ts default export, or a custom app's router script
export type RouterConfig = {
	// forwarded to createRouter; `routes` and `history` are withheld, Studio owns both
	routerOptions?: Omit<RouterOptions, "history" | "routes">
	// once per Studio page, with the plain vue-router record; mutate it
	extendRoute?: (route: RouteRecordRaw) => void
	// called once, awaited before app.use(router) and the first navigation
	setup?: (router: Router) => void | Promise<void>
}

const CONFIG_KEYS = ["routerOptions", "extendRoute", "setup"]

export class RouterScriptError extends Error {
	constructor(where: string, cause: unknown) {
		super(`${where}: ${cause instanceof Error ? cause.message : String(cause)}`, { cause })
	}
}

declare global {
	interface Window {
		app_name: string
		app_route: string
		app_pages: Page[]
		app_home?: string
		app_router_file?: string | null
		router_script?: string | null
		boot?: Record<string, unknown>
		is_guest?: boolean
	}
}

export async function createAppRouter(config: RouterConfig = {}): Promise<Router> {
	const unknownKeys = Object.keys(config).filter((key) => !CONFIG_KEYS.includes(key))
	if (unknownKeys.length) {
		throw new RouterScriptError("router config", `unknown keys ${unknownKeys.join(", ")}`)
	}
	const { routerOptions: options = {}, extendRoute } = config
	for (const key of ["routes", "history"]) {
		if (key in options) console.warn(`routerOptions.${key} is ignored, Studio owns it`)
	}
	const routes = getPageRoutes(window.app_pages)
	if (extendRoute) await runHook("extendRoute", () => routes.forEach((route) => extendRoute(route)))

	const router = createRouter({
		...options,
		history: createWebHistory(`/${window.app_route}`),
		routes,
	})
	await runHook("setup", () => config.setup?.(router))
	addHomeRouteFallback(router)
	addNotFoundRouteFallback(router)
	router.beforeEach(sendGuestToLogin)
	return router
}

// a custom app's router script comes with the page; a standard app's router.ts is imported from the
// vite dev server in the preview and compiled in by the production build
export async function loadRouterConfig(): Promise<RouterConfig> {
	if (window.router_script) return runHook("router script", () => compileRouterScript(window.router_script!))
	if (!window.app_router_file) return {}
	const mod = await runHook("router.ts", () => import(/* @vite-ignore */ window.app_router_file!))
	return mod.default || {}
}

// a broken router can drop a guard, so the app stops instead of booting with default routing
export function showRouterError(error: unknown) {
	console.error(error)
	createApp(RouterError, { message: error instanceof Error ? error.message : String(error) }).mount("#app")
}

async function runHook<T>(where: string, run: () => T | Promise<T>): Promise<T> {
	try {
		return await run()
	} catch (error) {
		throw error instanceof RouterScriptError ? error : new RouterScriptError(where, error)
	}
}

// the router.ts object without import/export, run like a custom page script: no module scope, so
// call/toast and the Vue reactivity APIs are put in scope (boot is a global already)
function compileRouterScript(source: string): RouterConfig {
	if (!source.trim()) return {}
	const factory = new Function("context", `with (context) { return (\n${source}\n) }`)
	return factory({ ...vueReactivityApis, ...globalUtils }) || {}
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
