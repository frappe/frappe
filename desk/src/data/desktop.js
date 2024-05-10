import { createResource } from "frappe-ui"

export const desktopItems = createResource({
	url: "frappe.api.desk.get_desktop_items",
	auto: true,
	transform: (data) => {
		return data.map((item) => {
			const slug = item.module.toLowerCase().replace(/ /g, "-")
			item.module_slug = slug
			return item
		})
	},
})

export async function getDesktopItem(slug) {
	if (!desktopItems.fetched) {
		await desktopItems.fetch()
	}

	return desktopItems.data.find((item) => item.module_slug === slug)
}
