import { createResource } from "frappe-ui"

export const vueComponents = createResource({
	url: "frappe.studio.api.get_custom_vue_components",
	method: "GET",
	// a GET serializes an undefined value as the string "undefined", so send only the key in use
	makeParams: ({ frappe_app, studio_app }: { frappe_app?: string; studio_app?: string }) =>
		studio_app ? { studio_app } : { frappe_app },
})
