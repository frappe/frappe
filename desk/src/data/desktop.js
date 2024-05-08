import { createResource } from "frappe-ui"

export const desktopItems = createResource({
	url: "frappe.api.desk.get_desktop_items",
	auto: true,
})
