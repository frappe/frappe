import "@/index.css"
import type { App } from "vue"

import { getWindowApp, type RouterConfig } from "@/router/app_router"
import { mountApp } from "@/mountApp"
import { registerGlobalComponents } from "@/globals"
import { registerCustomVueComponents } from "@/utils/customVueComponents"
import { loadAppRuntime, loadAppRouterConfig } from "@/browserRuntime/appRuntime"
import { registerStudioPageScripts } from "@/data/studioPageScripts"
import { registerStudioComponentScripts } from "@/data/studioComponentScripts"

declare global {
	interface Window {
		is_preview?: boolean
		is_db_app?: boolean
		can_edit_app?: boolean
		[key: string]: string
	}
}

if (window.is_preview && typeof window.is_preview === "string") {
	window.is_preview = window.is_preview === "1" || window.is_preview === "True"
}

const frappeApp = (window as any).frappe_app

// Load stored components and router.js before creating the database app's router.
async function prepareApp(vueApp: App): Promise<RouterConfig | undefined> {
	if (window.is_db_app) {
		await loadAppRuntime(window.app_name)
		return loadAppRouterConfig()
	}
	if (frappeApp) {
		await Promise.all([
			registerCustomVueComponents(frappeApp, window.app_name, vueApp._context.components),
			registerStudioPageScripts(frappeApp),
			registerStudioComponentScripts(frappeApp, window.app_name),
		])
	}
	return undefined
}

mountApp("#app", { app: getWindowApp(), setup: registerGlobalComponents, prepare: prepareApp })
