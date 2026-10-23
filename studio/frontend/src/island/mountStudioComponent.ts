import "@/setupFrappeUIResource"

import type { App } from "vue"
import { createPinia } from "pinia"
import { resourcesPlugin } from "frappe-ui"
import { mountVueIsland } from "@framework/ui/island"
import useComponentStore from "@/stores/componentStore"
import StudioComponentIsland from "@/island/StudioComponentIsland.vue"
import type { StudioComponent } from "@/types/Studio/StudioComponent"

interface StudioComponentIslandOptions {
	componentId: string
	componentDocs: StudioComponent[]
	registerComponents: (app: App) => void
}

export function mountStudioComponent(
	el: HTMLElement,
	context: { props?: Record<string, any> },
	{ componentId, componentDocs, registerComponents }: StudioComponentIslandOptions,
) {
	return mountVueIsland(el, {
		...context,
		component: StudioComponentIsland,
		props: { ...context.props, componentId },
		configure(app: App) {
			const pinia = createPinia()
			app.use(pinia)
			app.use(resourcesPlugin)
			registerComponents(app)
			// two islands on one page share this global, so add to it
			window.__APP_COMPONENTS__ = { ...window.__APP_COMPONENTS__, ...app._context.components }
			useComponentStore(pinia).setComponents(componentDocs)
		},
	})
}
