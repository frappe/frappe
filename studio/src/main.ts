import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "./setupFrappeUIResource"
import studio_router from "@/router/studio_router"
import App from "./App.vue"

import { resourcesPlugin, frappeRequest } from "frappe-ui"
import { spritePlugin } from "frappe-ui/icons"
import { registerGlobalComponents, registerCustomVueComponents } from "./globals"
import type { CustomVueComponentMeta } from "./globals"

import { COMPONENTS } from "@/data/components"
import Block from "@/utils/block"
import "@/utils/appUtilsRenderer"

Block.setComponents(COMPONENTS)

const studio = createApp(App)
const pinia = createPinia()

// For the main app builder
studio.use(studio_router)
studio.use(resourcesPlugin)
studio.use(spritePlugin)
studio.use(pinia)
registerGlobalComponents(studio)
window.__APP_COMPONENTS__ = studio._context.components

declare global {
	interface Window {
		site_url: string
		is_developer_mode?: boolean
		__APP_COMPONENTS__: any
		__CUSTOM_VUE_COMPONENTS__: CustomVueComponentMeta[]
		[key: string]: string
	}
}

if (window.is_developer_mode && typeof window.is_developer_mode === "string") {
	window.is_developer_mode = window.is_developer_mode === "1" || window.is_developer_mode === "True"
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

	const customComponents = await registerCustomVueComponents(studio)
	window.__CUSTOM_VUE_COMPONENTS__ = customComponents

	studio.mount("#studio")
})