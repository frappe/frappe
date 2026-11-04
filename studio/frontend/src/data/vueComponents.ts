import { createResource } from "frappe-ui"

export const vueComponents = createResource({
	url: "frappe.studio.api.get_custom_vue_components",
	method: "GET",
	// Omit unused keys because GET parameters would serialize undefined as the text "undefined".
	makeParams: ({ frappe_app, studio_app }: { frappe_app?: string; studio_app?: string }) =>
		studio_app ? { studio_app } : { frappe_app },
})
