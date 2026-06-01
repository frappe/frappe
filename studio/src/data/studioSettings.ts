import { createDocumentResource } from "frappe-ui"

export const studioSettings = createDocumentResource({
	doctype: "Studio Settings",
	name: "Studio Settings",
	auto: true,
})
