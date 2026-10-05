import {
	createRouter,
	createWebHistory,
	type RouteRecordRaw,
	type Router,
	type RouterOptions,
} from "vue-router"
import AppContainer from "@/pages/AppContainer.vue"
import NotFound from "@/pages/NotFound.vue"
import * as globalUtils from "@/utils/globalUtils"

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

declare global {
	interface Window {
		app_name: string
		app_route: string
		app_pages: Page[]
		app_home?: string
		router_file?: string | null
		router_script?: string | null
		boot?: Record<string, unknown>
		is_guest?: boolean
	}
}

export async function createAppRouter(config?: RouterConfig): Promise<Router> {
	config ??= await loadRouterConfig()
	const unknownKeys = Object.keys(config).filter((key) => !CONFIG_KEYS.includes(key))
	if (unknownKeys.length) {
		throw new Error(`router config: unknown keys ${unknownKeys.join(", ")}`)
	}
	const { routerOptions: options = {}, extendRoute } = config
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

// custom app: the Studio App's router script; standard app: router.ts
async function loadRouterConfig(): Promise<RouterConfig> {
	if (window.router_script) return runHook("router script", () => compileRouterScript(window.router_script!))
	if (!window.router_file) return {}
	const mod = await runHook("router.ts", () => import(/* @vite-ignore */ window.router_file!))
	return mod.default || {}
}

function compileRouterScript(source: string): RouterConfig {
	const factory = new Function("context", `with (context) { return (\n${source}\n) }`)
	return factory({ ...globalUtils }) || {}
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

async function runHook<T>(where: string, run: () => T | Promise<T>): Promise<T> {
	try {
		return await run()
	} catch (error) {
		const message = error instanceof Error ? `${error.name}: ${error.message}` : String(error)
		throw new Error(`${where}: ${message}`, { cause: error })
	}
}
