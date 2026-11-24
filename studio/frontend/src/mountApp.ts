import { createApp, type App } from "vue"
import { createPinia, disposePinia } from "pinia"
import { resourcesPlugin } from "frappe-ui"
import "@/setupFrappeUIResource"
import AppRenderer from "@/AppRenderer.vue"
import ErrorPage from "@/pages/ErrorPage.vue"
import { createAppRouter, type RendererApp, type RouterConfig } from "@/router/app_router"
import { initSocket } from "@/socket"
import { disposePageLoader } from "@/page/pageLoader"
import type { Socket } from "socket.io-client"

export type InstallOptions = {
	setup?: (vueApp: App) => void
	socket?: Socket | null
}

export type MountOptions = InstallOptions & {
	app: RendererApp
	prepare?: (vueApp: App) => Promise<RouterConfig | undefined>
}

export function installApp(vueApp: App, { setup, socket: suppliedSocket }: InstallOptions): () => void {
	const socket = suppliedSocket === undefined ? initSocket() : suppliedSocket
	const pinia = createPinia()
	vueApp.use(pinia)
	vueApp.provide("vueApp", vueApp)
	vueApp.use(resourcesPlugin)
	vueApp.provide("socket", socket)
	setup?.(vueApp)
	vueApp.provide("appComponents", vueApp._context.components)
	return () => {
		disposePinia(pinia)
		if (suppliedSocket === undefined) socket?.disconnect()
	}
}

export async function mountApp(
	el: Element | string,
	{ app, prepare, ...options }: MountOptions,
): Promise<() => void> {
	const vueApp = createApp(AppRenderer)
	const dispose = installApp(vueApp, options)

	try {
		const router = await createAppRouter(await prepare?.(vueApp), app)
		vueApp.use(router).mount(el)
		return () => {
			disposePageLoader(router)
			vueApp.unmount()
			dispose()
		}
	} catch (error) {
		console.error(error)
		const errorApp = createApp(ErrorPage, { error })
		errorApp.mount(el)
		return () => {
			errorApp.unmount()
			dispose()
		}
	}
}
