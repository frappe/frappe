import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "./setupFrappeUIResource"
import studio_router from "@/router/studio_router"
import App from "./App.vue"

import { resourcesPlugin, frappeRequest } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

import { COMPONENTS } from "@/data/components"
import Block from "@/utils/block"
Block.setComponents(COMPONENTS)

const studio = createApp(App)
const pinia = createPinia()

// For the main app builder
studio.use(studio_router)
studio.use(resourcesPlugin)
studio.use(pinia)
registerGlobalComponents(studio)
window.__APP_COMPONENTS__ = studio._context.components

declare global {
	interface Window {
		site_url: string
		__APP_COMPONENTS__: any
		[key: string]: string
	}
}

studio_router.isReady().then(async () => {
	if (import.meta.env.DEV) {
		await frappeRequest({
			url: "/api/method/studio.www.studio.get_context_for_dev",
		}).then(async (values: Record<string, any>) => {
			for (let key in values) {
				window[key] = values[key]
			}
		})
	}
	studio.mount("#studio")
})