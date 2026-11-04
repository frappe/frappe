import { createMemoryHistory, createRouter, type RouteRecordRaw, type Router } from "vue-router"
import type { StudioPage } from "@/types/Studio/StudioPage"

// never rendered: this router only matches and resolves, the editor draws the canvas itself
const NO_COMPONENT = { render: () => null }

// The editor's own router describes /studio/app/…, not the app being built. Page scripts get this
// one instead, over the app's own pages, so nothing a script navigates takes the editor with it.
export function createEditorAppRouter() {
	const router: Router = createRouter({ history: createMemoryHistory(), routes: [] })
	let removeRoutes: (() => void)[] = []

	function goToPage(pages: StudioPage[], page: StudioPage, params: Record<string, string>) {
		setAppRoutes(pages)
		if (page.route) router.replace(fillRoute(page.route, params))
	}

	// addRoute returns its own remover, so rebuilding does not rely on route names being unique
	function setAppRoutes(pages: StudioPage[]) {
		removeRoutes.forEach((remove) => remove())
		const names = new Set<string>()
		removeRoutes = pages.map((page) => addRoute(pageRoute(page, names)))
		// as addNotFoundRouteFallback does for the rendered app: an unset route variable leaves a path
		// like /articles/ that matches no page. Unnamed, so a page titled "Not Found" cannot replace it.
		removeRoutes.push(addRoute({ path: "/:pathMatch(.*)*", component: NO_COMPONENT, meta: { notFound: true } }))
	}

	// a page's route is whatever the user has typed so far, and vue-router rejects a half-written
	// pattern such as /articles/:name( — one of those must not take the whole editor down
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

// Mirrors getPageRoutes in app_router.ts, so a script resolves a page as it does in the rendered
// app. Two pages can share a title while being edited and addRoute drops the earlier one's path, so
// a repeated title falls back to the docname.
function pageRoute(page: StudioPage, names: Set<string>): RouteRecordRaw {
	const name = page.page_title && !names.has(page.page_title) ? page.page_title : page.name
	names.add(name)
	return { path: page.route, name, component: NO_COMPONENT, meta: { pageName: page.name } }
}

// Encoded, as router.resolve would: a docname like INV/2024/00001 has to stay one path segment.
function fillRoute(route: string, params: Record<string, string>) {
	return route
		.split("/")
		.map((part) => (part.startsWith(":") && part.length > 1 ? encodeURIComponent(params[part.slice(1)] ?? "") : part))
		.join("/")
}
