import "@/index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "@/setupFrappeUIResource"
import app_router from "@/router/app_router"
import AppRenderer from "@/AppRenderer.vue"
import { resourcesPlugin } from "frappe-ui"
import { spritePlugin } from "frappe-ui/icons"
import { registerGlobalComponents, registerCustomVueComponents } from "@/globals"
import "@/utils/appUtils"

// For rendering apps built by studio
const app = createApp(AppRenderer)
const pinia = createPinia()

app.use(app_router)
app.use(pinia)
app.use(resourcesPlugin)
app.use(spritePlugin)
registerGlobalComponents(app)
window.__APP_COMPONENTS__ = app._context.components

const frappeApp = (window as any).frappe_app
if (frappeApp) {
	registerCustomVueComponents(app, frappeApp).then(() => {
		app.mount("#app")
	})
} else {
	app.mount("#app")
}