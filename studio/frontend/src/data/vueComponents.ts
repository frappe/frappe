import { createResource } from "frappe-ui"

export const vueComponents = createResource({
	url: "frappe.studio.api.get_custom_vue_components",
	method: "GET",
	makeParams: ({ frappe_app }: { frappe_app: string }) => ({ frappe_app }),
})
