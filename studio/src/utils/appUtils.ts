import app_router from "@/router/app_router"

declare global {
	interface Window {
		studio: {
			utils?: object
		}
	}
}

if (typeof window.studio === 'undefined') {
	window.studio = {}
}

const utils = {
	navigateToPage: (pageName: string) => {
		app_router.push({ name: pageName })
	}
}

window.studio.utils = utils