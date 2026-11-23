import { inject, shallowRef, watch, type App, type ShallowRef } from "vue"
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

const pageLoaders = new WeakMap<Router, { loadedPages: Map<string, LoadedPage>; latestNavigation: number }>()

// beforeResolve guard: load the next page before the navigation completes. The page being left
// stays untouched meanwhile, and the new page mounts with every binding already resolved.
export async function loadPage(router: Router, to: RouteLocationNormalized, from: RouteLocationNormalized) {
	const state = getPageLoader(router)
	const navigation = ++state.latestNavigation
	const pageName = to.meta.pageName as string | undefined
	if (!pageName) return
	// same page, new params: the mounted page follows its route. A forced replace (preview reload) loads afresh.
	if (pageName === from.meta.pageName && to.fullPath !== from.fullPath) return

	const vueApp = inject<App>("vueApp")!
	const registeredComponents = inject("appComponents", {})
	const componentStore = useComponentStore()
	const appName = to.meta.appName as string
	const page = await fetchAppPage(appName, pageName, Boolean(window.is_preview))
	if (navigation !== state.latestNavigation) return
	if (!page) return redirectToNotFound(router, to)

	const pageRoute = shallowRef(to)
	const scope = createPageScope(pageRoute, shallowRef(router), registeredComponents)
	try {
		await scope.setPageVariables(page, page.variables)
		await scope.setPageResources(page, false, page.resources)
		if (navigation !== state.latestNavigation) return scope.teardownPage()
		await scope.loadPageScript(page)
		if (navigation !== state.latestNavigation) return scope.teardownPage()
		// before the block tree, so no block fetches its component (Guests can't read Studio Component)
		componentStore.setStudioApp(appName)
		await componentStore.setComponents(page.components || [])
		if (navigation !== state.latestNavigation) return scope.teardownPage()
		const root = vueApp.runWithContext(() => getBlockInstance(JSON.parse(page.blocks)[0]))
		state.loadedPages.set(to.fullPath, { page, scope, pageRoute, root })
	} catch (error) {
		scope.teardownPage()
		throw error
	}
}

export function disposePageLoader(router: Router) {
	const state = getPageLoader(router)
	state.latestNavigation++
	for (const { scope } of state.loadedPages.values()) scope.teardownPage()
	state.loadedPages.clear()
}

// afterEach: a navigation that did not go through drops the page it loaded
export function discardPage(router: Router, to: RouteLocationNormalized, failure: unknown) {
	if (!failure) return
	const { loadedPages } = getPageLoader(router)
	loadedPages.get(to.fullPath)?.scope.teardownPage()
	loadedPages.delete(to.fullPath)
}

// AppPage setup: hand over the page loaded for the current route
export function useLoadedPage(): LoadedPage {
	const router = useRouter()
	const { loadedPages } = getPageLoader(router)
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

function getPageLoader(router: Router) {
	if (!pageLoaders.has(router)) {
		pageLoaders.set(router, { loadedPages: new Map(), latestNavigation: 0 })
	}
	return pageLoaders.get(router)!
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
