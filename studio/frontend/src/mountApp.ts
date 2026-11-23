import { createApp, type App } from "vue"
import { createPinia, disposePinia } from "pinia"
import { resourcesPlugin } from "frappe-ui"
import "@/setupFrappeUIResource"
import AppRenderer from "@/AppRenderer.vue"
import ErrorPage from "@/pages/ErrorPage.vue"
import { createAppRouter, type RendererApp, type RouterConfig } from "@/router/app_router"
import { initSocket } from "@/socket"
import { disposePageLoader } from "@/page/pageLoader"

export type MountOptions = {
	app: RendererApp
	setup?: (vueApp: App) => void
	prepare?: (vueApp: App) => Promise<RouterConfig | undefined>
}

export async function mountApp(el: Element | string, { app, setup, prepare }: MountOptions): Promise<() => void> {
	const socket = initSocket()
	const vueApp = createApp(AppRenderer)
	const pinia = createPinia()
	vueApp.use(pinia)
	vueApp.provide("vueApp", vueApp)
	vueApp.use(resourcesPlugin)
	vueApp.provide("socket", socket)
	setup?.(vueApp)
	vueApp.provide("appComponents", vueApp._context.components)

	try {
		const router = await createAppRouter(await prepare?.(vueApp), app)
		vueApp.use(router).mount(el)
		return () => {
			disposePageLoader(router)
			vueApp.unmount()
			disposePinia(pinia)
			socket.disconnect()
		}
	} catch (error) {
		console.error(error)
		const errorApp = createApp(ErrorPage, { error })
		errorApp.mount(el)
		return () => {
			errorApp.unmount()
			disposePinia(pinia)
			socket.disconnect()
		}
	}
}
