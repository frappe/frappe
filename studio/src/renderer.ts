import "@/index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/setupFrappeUIResource"
import app_router from "@/router/app_router"
import AppRenderer from "@/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { spritePlugin } from "frappe-ui/icons"
import { registerGlobalComponents, registerCustomVueComponents } from "@/globals"
import { registerStudioPageScripts } from "@/data/studioPageScripts"

// For rendering apps built by studio
const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)
app.use(spritePlugin)
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

const frappeApp = (window as any).frappe_app
if (frappeApp) {
	Promise.all([
		registerCustomVueComponents(frappeApp),
		registerStudioPageScripts(frappeApp),
	]).then(() => {
		app.mount("#app")
	})
} else {
	app.mount("#app")
}