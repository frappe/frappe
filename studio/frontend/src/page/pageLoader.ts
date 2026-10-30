import { ref, shallowRef, watch, type InjectionKey, type ShallowRef } from "vue"
import { useRouter, type Router, type RouteLocationNormalized } from "vue-router"
import { fetchAppPage } from "@/utils/helpers"
import { getBlockInstance } from "@/utils/serializer"
import { createPageScope, type PageScope } from "@/page/pageScope"
import useComponentStore from "@/stores/componentStore"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type Block from "@/utils/block"

export type LoadedPage = {
	page: StudioPage
	scope: PageScope
	pageRoute: ShallowRef<RouteLocationNormalized>
	root: Block
}

const loadedPages = new Map<string, LoadedPage>()
const refreshing = new Map<string, Promise<void>>()
let latestNavigation = 0

// Bumped only where a page is staged, so a remount always finds one. The renderer keys the
// page component on it: re-reading a page leaves the fresh copy here, this makes it mount.
export const pageRevision = ref(0)

/** Provided by the renderer root: re-read the open page. A component that changed the page on
 * the server injects this; nothing else can remount the page, so there is no sensible fallback. */
export const refreshPageKey: InjectionKey<() => Promise<void>> = Symbol("refreshPage")

// beforeResolve guard: load the next page before the navigation completes. The page being left
// stays untouched meanwhile, and the new page mounts with every binding already resolved.
export async function loadPage(router: Router, to: RouteLocationNormalized, from: RouteLocationNormalized) {
	const pageName = to.meta.pageName as string | undefined
	if (!pageName) return
	// same page, new params: the mounted page follows its route, so nothing is reloaded
	if (pageName === from.meta.pageName && to.fullPath !== from.fullPath) return
	return preparePage(router, to)
}

/** Read the open page again, for a caller that changed it on the server. A Keep and the save
 * notice it triggers both ask for the same re-read, so callers share the one in flight. */
export function reloadCurrentPage(router: Router): Promise<void> {
	const { fullPath } = router.currentRoute.value
	const running = refreshing.get(fullPath)
	if (running) return running

	const refresh = (async () => {
		const redirect = await preparePage(router, router.currentRoute.value, true)
		if (redirect) await router.replace(redirect)
	})().finally(() => refreshing.delete(fullPath))
	refreshing.set(fullPath, refresh)
	return refresh
}

async function preparePage(router: Router, route: RouteLocationNormalized, fresh = false) {
	const navigation = ++latestNavigation
	const pageName = route.meta.pageName as string
	// a published definition is cached, so only a refresh pays for a fresh read of it
	const page = await fetchAppPage(window.app_name, pageName, Boolean(window.is_preview), fresh)
	if (navigation !== latestNavigation) return
	if (!page) return redirectToNotFound(router, route)

	const pageRoute = shallowRef(route)
	const scope = createPageScope(pageRoute, shallowRef(router))
	try {
		await scope.setPageVariables(page, page.variables)
		await scope.setPageResources(page, false, page.resources)
		if (navigation !== latestNavigation) return scope.teardownPage()
		await scope.setPageScript(page, Boolean(page.is_standard))
		if (navigation !== latestNavigation) return scope.teardownPage()
		// before the block tree, so no block fetches its component (Guests can't read Studio Component)
		useComponentStore().setComponents(page.components || [])
		const root = getBlockInstance(JSON.parse(page.blocks)[0])
		loadedPages.set(route.fullPath, { page, scope, pageRoute, root })
		pageRevision.value++
	} catch (error) {
		scope.teardownPage()
		throw error
	}
}

// afterEach: a navigation that did not go through drops the page it loaded
export function discardPage(to: RouteLocationNormalized, failure: unknown) {
	if (!failure) return
	loadedPages.get(to.fullPath)?.scope.teardownPage()
	loadedPages.delete(to.fullPath)
}

// AppPage setup: hand over the page loaded for the current route
export function useLoadedPage(): LoadedPage {
	const router = useRouter()
	const fullPath = router.currentRoute.value.fullPath
	const loaded = loadedPages.get(fullPath)
	if (!loaded) throw new Error(`No page was loaded for ${fullPath}`)
	loadedPages.delete(fullPath)
	// the page's own route follows param changes on this page only, so leaving it never refetches
	// its resources with the next page's params
	watch(router.currentRoute, (to) => {
		if (to.meta.pageName === loaded.page.name) loaded.pageRoute.value = to
	})
	return loaded
}

function redirectToNotFound(router: Router, to: RouteLocationNormalized) {
	if (!router.hasRoute("Not Found")) return false
	return {
		name: "Not Found",
		params: { pathMatch: to.path.slice(1).split("/") },
		query: to.query,
		hash: to.hash,
		replace: true,
	}
}
