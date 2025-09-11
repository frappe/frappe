import studio_router from "@/router/studio_router"
import { toast } from "vue-sonner"
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
		return studio_router.push(to)
	},
	showToast: ({ title, message, type }: {
		title?: string
		message: string
		type?: 'info' | 'success' | 'warning' | 'error'
	}) => {
		const toastMessage = title || message
		const description = title ? message : undefined

		switch (type?.toLowerCase()) {
			case 'success':
				return toast.success(toastMessage, { description })
			case 'error':
				return toast.error(toastMessage, { description })
			case 'warning':
				return toast.warning(toastMessage, { description })
			case 'info':
				return toast.info(toastMessage, { description })
			default:
				return toast(toastMessage, { description })
		}
	},
}

Object.assign(window.studio, utils)