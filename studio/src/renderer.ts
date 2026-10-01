import "@/index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/setupFrappeUIResource"
import { createAppRouter, loadRouterConfig, showRouterError } from "@/router/app_router"
import AppRenderer from "@/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { registerGlobalComponents, registerCustomVueComponents } from "@/globals"
import { registerStudioPageScripts } from "@/data/studioPageScripts"
import { initSocket } from "@/socket"

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
		is_developer_mode?: boolean
		is_preview?: boolean
		__APP_COMPONENTS__: any
		[key: string]: string
	}
}

if (window.is_preview && typeof window.is_preview === "string") {
	window.is_preview = window.is_preview === "1" || window.is_preview === "True"
}

async function bootstrap() {
	const frappeApp = (window as any).frappe_app
	if (frappeApp) {
		await Promise.all([registerCustomVueComponents(frappeApp), registerStudioPageScripts(frappeApp)])
	}
	// installing the router runs the first navigation, so the app's guards must already be in place
	try {
		app.use(await createAppRouter(await loadRouterConfig()))
	} catch (error) {
		return showRouterError(error)
	}
	app.mount("#app")
}

bootstrap()