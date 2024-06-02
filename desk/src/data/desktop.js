import { createResource } from "frappe-ui"
import { slug, getRoute } from "@/utils/routing"

export const desktopItems = createResource({
	url: "frappe.api.desk.get_desktop_items",
	initialData: [],
	auto: true,
	transform: (data) => {
		return data.map((item) => {
			item.module_slug = slug(item.module)
			return item
		})
	},
})

export const sidebar = createResource({
	url: "frappe.desk.doctype.module_sidebar.module_sidebar.get_module_sidebar",
	transform(data) {
		data.workspaces.forEach((workspace) => {
			workspace.route_to = getRoute(workspace, data.module)
		})

		data.sections.forEach((item) => {
			if (item.type === "Section Break") {
				item.opened = true
				item.links.forEach((link) => {
					link.route_to = getRoute(link, data.module)
				})
			} else if (item.type === "Link") {
				item.route_to = getRoute(item, data.module)
			}
		})
		return data
	},
})

export async function getDesktopItem(module) {
	if (!desktopItems.fetched) {
		await desktopItems.fetch()
	}

	return desktopItems.data.find((item) => item.module === module)
}
