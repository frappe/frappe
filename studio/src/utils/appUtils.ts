import app_router from "@/router/app_router"
import type { RouteLocationRaw } from "vue-router"

declare global {
	interface Window {
		studio: Record<string, any>
	}
}

if (typeof window.studio === 'undefined') {
	window.studio = {}
}

const utils = {
	navigate: (to: RouteLocationRaw) => {
		return app_router.push(to)
	},
}

Object.assign(window.studio, utils)