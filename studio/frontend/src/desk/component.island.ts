import { createPinia } from "pinia"
import { mountVueIsland } from "@framework/ui/island"
import "@/setupFrappeUIResource"
import { registerGlobalComponents } from "@/globals"
import DeskComponent from "@/desk/DeskComponent.vue"

/** Mount a global Studio component. Props: `component`, the component's id, and `props`, its prop values. */
export function mount(el: HTMLElement, context: Record<string, any>) {
	// frappe-ui sends the token from here, and desk keeps it on `frappe`
	window.csrf_token ||= (window as any).frappe?.csrf_token
	return mountVueIsland(el, {
		...context,
		component: DeskComponent,
		configure(app: any) {
			app.use(createPinia())
			registerGlobalComponents(app)
			// a block reads the component that it draws from here, as it does in the renderer
			window.__APP_COMPONENTS__ = app._context.components
		},
	})
}
