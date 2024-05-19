import { createResource } from "frappe-ui"
import { slug } from "@/utils/routing"

// FIXME: first request fails with resourceFetcher - calls desk/api/method instead of /api/method
export const desktopItems = createResource({
	url: "frappe.api.desk.get_desktop_items",
	initialData: [],
	auto: true,
	cache: "desktopItems",
	transform: (data) => {
		return data.map((item) => {
			item.module_slug = slug(item.module)
			return item
		})
	},
})

export const sidebar = createResource({
	url: "frappe.api.desk.get_module_sidebar",
	transform(data) {
		data.sections.forEach((item) => {
			if (item.type === "Section Break") {
				item.opened = true
			}
		})
		return data
	},
})

export async function getDesktopItem(slug) {
	if (!desktopItems.fetched) {
		await desktopItems.fetch()
	}

	return desktopItems.data.find((item) => item.module_slug === slug)
}
