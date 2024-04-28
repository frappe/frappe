import { createResource } from "frappe-ui"

export const desktopModules = createResource({
	url: "frappe.desk.desktop.get_workspace_sidebar_items",
	auto: true,
})
