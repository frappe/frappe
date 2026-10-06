import { shallowRef, type ShallowRef } from "vue"
import type { Router, RouteLocationNormalized } from "vue-router"
import { fetchAppPage } from "@/utils/helpers"
import { getBlockInstance } from "@/utils/serializer"
import { createPageScope, type PageScope } from "@/stores/pageScope"
import type { StudioPage } from "@/types/Studio/StudioPage"
import type Block from "@/utils/block"

export type PreparedPage = {
	page: StudioPage
	scope: PageScope
	pageRoute: ShallowRef<RouteLocationNormalized>
	root: Block
}

const preparedPages = new Map<string, PreparedPage>()
let latestNavigation = 0

// beforeResolve guard: build the next page's scope before the navigation completes. The page being
// left stays untouched meanwhile, and the new page mounts with every binding already resolved.
export async function preparePage(router: Router, to: RouteLocationNormalized, from: RouteLocationNormalized) {
	const navigation = ++latestNavigation
	const pageName = to.meta.pageName as string | undefined
	if (!pageName) return
	// same page, new params: the mounted page follows its route. A forced replace (preview reload) gets a fresh scope.
	if (pageName === from.meta.pageName && to.fullPath !== from.fullPath) return

	const page = await fetchAppPage(window.app_name, pageName, Boolean(window.is_preview))
	if (navigation !== latestNavigation) return
	if (!page) return notFoundFor(router, to)

	const pageRoute = shallowRef(to)
	const scope = createPageScope(pageRoute, shallowRef(router))
	await scope.setPageVariables(page, page.variables)
	await scope.setPageResources(page, false, page.resources)
	await scope.setPageScript(page, Boolean(page.is_standard))
	if (navigation !== latestNavigation) return scope.teardownPage()

	const root = getBlockInstance(JSON.parse(page.blocks)[0])
	preparedPages.set(to.fullPath, { page, scope, pageRoute, root })
}

// afterEach: a navigation that did not go through discards what it prepared
export function discardPreparedPage(to: RouteLocationNormalized, failure: unknown) {
	latestNavigation++
	if (!failure) return
	preparedPages.get(to.fullPath)?.scope.teardownPage()
	preparedPages.delete(to.fullPath)
}

export function takePreparedPage(fullPath: string): PreparedPage {
	const prepared = preparedPages.get(fullPath)
	if (!prepared) throw new Error(`No page was prepared for ${fullPath}`)
	preparedPages.delete(fullPath)
	return prepared
}

function notFoundFor(router: Router, to: RouteLocationNormalized) {
	if (!router.hasRoute("Not Found")) return false
	return {
		name: "Not Found",
		params: { pathMatch: to.path.slice(1).split("/") },
		query: to.query,
		hash: to.hash,
		replace: true,
	}
}
