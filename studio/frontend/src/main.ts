import "./index.css"

import { createApp } from "vue"
import { createPinia } from "pinia"
import "./setupFrappeUIResource"
import studio_router from "@/router/studio_router"
import App from "./App.vue"

import { resourcesPlugin, frappeRequest, setConfig, toast } from "frappe-ui"
import { registerGlobalComponents } from "./globals"

import { COMPONENTS } from "@/data/components"
import Block from "@/utils/block"
import { componentHasDefaultSlot } from "@/utils/componentSlots"
import { initSocket } from "@/socket"

Block.setComponents(COMPONENTS)
Block.setDefaultSlotLookup(componentHasDefaultSlot)

// Show what the server reports about a request that succeeded, such as a warning on save.
setConfig("serverMessagesHandler", (messages: string[]) => {
	// after the caller's own toast, which would cover these
	setTimeout(() => {
		for (const { title, message, indicator } of messages.map((entry) => JSON.parse(entry))) {
			const show = indicator === "orange" ? toast.warning : toast.info
			show(title || message, { description: title ? message : undefined, duration: 10000 })
		}
	})
})

const studio = createApp(App)
const pinia = createPinia()
studio.provide("vueApp", studio)

// For the main app builder
studio.use(studio_router)
studio.use(resourcesPlugin)
studio.use(pinia)
registerGlobalComponents(studio)
studio.provide("appComponents", studio._context.components)

declare global {
	interface Window {
		site_url: string
		is_developer_mode?: boolean
		[key: string]: string
	}
}

if (window.is_developer_mode && typeof window.is_developer_mode === "string") {
	// an unrendered "{{ ... }}" means the Vite dev server, which needs developer mode
	window.is_developer_mode =
		window.is_developer_mode === "1" ||
		window.is_developer_mode === "True" ||
		(window.is_developer_mode as string).startsWith("{{")
}

let socket
studio_router.isReady().then(async () => {
	if (import.meta.env.DEV) {
		await frappeRequest({
			url: "/api/method/frappe.www.studio.get_context_for_dev",
		}).then(async (values: Record<string, any>) => {
			for (let key in values) {
				window[key] = values[key]
			}
			socket = initSocket()
			studio.provide("socket", socket)
			studio.mount("#studio")
		})
	} else {
		socket = initSocket()
		studio.provide("socket", socket)
		studio.mount("#studio")
	}
})
