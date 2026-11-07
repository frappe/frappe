import { createMemoryHistory, createRouter, type RouteRecordRaw, type Router } from "vue-router"
import type { StudioPage } from "@/types/Studio/StudioPage"

// The editor renders the canvas itself; this router only matches and resolves app routes.
const NO_COMPONENT = { render: () => null }

// Give page scripts a memory router for the app's pages. Script navigation must not change
// the editor's own /studio/app/... route.
export function createEditorAppRouter() {
	const router: Router = createRouter({ history: createMemoryHistory(), routes: [] })
	let removeRoutes: (() => void)[] = []

	function goToPage(pages: StudioPage[], page: StudioPage, params: Record<string, string>) {
		setAppRoutes(pages)
		if (page.route) router.replace(fillRoute(page.route, params))
	}

	// Use addRoute's removal callbacks so cleanup also handles unnamed routes.
	function setAppRoutes(pages: StudioPage[]) {
		removeRoutes.forEach((remove) => remove())
		const names = new Set<string>()
		removeRoutes = pages.map((page) => addRoute(pageRoute(page, names)))
		// Unset test parameters can produce unmatched paths such as /articles/.
		// Leave the fallback unnamed so a page titled "Not Found" cannot replace it.
		removeRoutes.push(addRoute({ path: "/:pathMatch(.*)*", component: NO_COMPONENT, meta: { notFound: true } }))
	}

	// Routes can be incomplete while editing, for example /articles/:name(.
	// Keep the editor usable when Vue Router rejects a route pattern.
	function addRoute(route: RouteRecordRaw) {
		try {
			return router.addRoute(route)
		} catch (error) {
			console.warn(`Studio: ignoring invalid page route "${route.path}"`, error)
			return () => {}
		}
	}

	return { router, goToPage }
}

// Use page titles as route names, as getPageRoutes does for the rendered app.
// While editing, duplicate titles use the page record name so addRoute keeps both routes.
function pageRoute(page: StudioPage, names: Set<string>): RouteRecordRaw {
	const name = page.page_title && !names.has(page.page_title) ? page.page_title : page.name
	names.add(name)
	return { path: page.route, name, component: NO_COMPONENT, meta: { pageName: page.name } }
}

// Encode parameter values so a record name such as INV/2024/00001 remains one path segment.
function fillRoute(route: string, params: Record<string, string>) {
	return route
		.split("/")
		.map((part) => (part.startsWith(":") && part.length > 1 ? encodeURIComponent(params[part.slice(1)] ?? "") : part))
		.join("/")
}
