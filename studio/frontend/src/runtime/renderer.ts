import "@/runtime/index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/runtime/setupFrappeUIResource"
import { createAppRouter, type RouterConfig } from "@/runtime/router/app_router"
import ErrorPage from "@/runtime/pages/ErrorPage.vue"
import AppRenderer from "@/runtime/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents } from "@/runtime/globals"
import { registerCustomVueComponents } from "@/runtime/utils/customVueComponents"
import { loadAppRuntime, loadAppRouterConfig } from "@/runtime/browserRuntime/appRuntime"
import { registerStudioPageScripts } from "@/runtime/data/studioPageScripts"
import { registerStudioComponentScripts } from "@/runtime/data/studioComponentScripts"
import { initSocket } from "@/runtime/socket"

// For rendering apps built by studio
const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(pinia)
app.use(resourcesPlugin)
app.provide("socket", initSocket())
registerGlobalComponents(app)
window.__APP_COMPONENTS__ = app._context.components

declare global {
	interface Window {
		is_preview?: boolean
		is_db_app?: boolean
		can_edit_app?: boolean
		__APP_COMPONENTS__: any
		[key: string]: string
	}
}

if (window.is_preview && typeof window.is_preview === "string") {
	window.is_preview = window.is_preview === "1" || window.is_preview === "True"
}

const frappeApp = (window as any).frappe_app

// Load stored components and router.js before creating the database app's router.
async function prepareApp(): Promise<RouterConfig | undefined> {
	if (window.is_db_app) {
		await loadAppRuntime(window.app_name)
		return loadAppRouterConfig()
	}
	if (frappeApp) {
		await Promise.all([
			registerCustomVueComponents(frappeApp, window.app_name),
			registerStudioPageScripts(frappeApp),
			registerStudioComponentScripts(frappeApp, window.app_name),
		])
	}
	return undefined
}

prepareApp()
	.then((routerConfig) => createAppRouter(routerConfig))
	.then((router) => app.use(router).mount("#app"))
	.catch((error) => {
		console.error(error)
		createApp(ErrorPage, { error }).mount("#app")
	})
