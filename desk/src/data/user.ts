import router from "@/router"
import { Resource } from "@/types/frappeUI"
import { createResource } from "frappe-ui"

export const user: Resource = createResource({
	url: "frappe.api.desk.get_current_user_info",
	cache: "frappe:user",
	onError(error: any) {
		if (error?.exc_type === "AuthenticationError") {
			router.push({ name: "Login" })
		}
	},
})
