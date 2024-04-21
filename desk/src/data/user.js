import { createResource } from "frappe-ui"

export const user = createResource({
	url: "frappe.api.desk.get_current_user_info",
	cache: "frappe:user",
	onError(error) {
		if (error && error.exc_type === "AuthenticationError") {
			router.push({ name: "Login" })
		}
	},
})
