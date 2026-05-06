import { createResource } from "frappe-ui"

export const vueComponents = createResource({
	url: "studio.api.get_custom_vue_components",
	makeParams: ({ frappe_app }: { frappe_app: string }) => {
		return {
			frappe_app: frappe_app
		}
	},
})