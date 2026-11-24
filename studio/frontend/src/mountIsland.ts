import type { App } from "vue"
import { createMemoryHistory } from "vue-router"
import { frappeRequest } from "frappe-ui"
import { mountVueIsland } from "@framework/ui/island"
import StudioIsland from "@/StudioIsland.vue"
import { installApp } from "@/mountApp"
import { createAppRouter, type RendererApp, type RouterConfig } from "@/router/app_router"
import { disposePageLoader } from "@/page/pageLoader"
import { islandPath, type IslandRoute } from "@/utils/islandRoute"

type IslandContext = {
	host?: Record<string, any>
	props?: IslandRoute & Record<string, unknown>
	styles?: string[]
}

type IslandOptions = {
	appName: string
	setup: (vueApp: App) => void
	routerConfig?: RouterConfig
}

export async function mountIsland(
	el: HTMLElement,
	context: IslandContext,
	{ appName, setup, routerConfig }: IslandOptions,
) {
	const app: RendererApp = await frappeRequest({
		url: "/api/method/frappe.studio.api.get_island_app",
		method: "GET",
		params: { app_name: appName },
	})
	const history = createMemoryHistory()
	history.replace(islandPath(context.props || {}))
	const router = await createAppRouter(routerConfig, { ...app, history })

	let dispose = () => {}
	const island = await mountVueIsland(el, {
		...context,
		component: StudioIsland,
		router,
		configure: (vueApp: App) => {
			dispose = installApp(vueApp, { setup, socket: context.host?.socket ?? null })
		},
	}).catch((error) => {
		disposePageLoader(router)
		dispose()
		throw error
	})
	return {
		update: island.update,
		unmount() {
			disposePageLoader(router)
			island.unmount()
			dispose()
		},
	}
}
