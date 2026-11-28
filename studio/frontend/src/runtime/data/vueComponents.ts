import { createResource } from "frappe-ui"

export const vueComponents = createResource({
	url: "frappe.studio.api.get_custom_vue_components",
	method: "GET",
	makeParams: ({ frappe_app, studio_app }: { frappe_app: string; studio_app: string }) => ({
		frappe_app,
		studio_app,
	}),
})
