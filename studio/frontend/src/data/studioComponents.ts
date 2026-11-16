import { createListResource } from "frappe-ui"

const studioComponents = createListResource({
	method: "GET",
	doctype: "Studio Component",
	fields: ["component_id", "component_name", "creation", "modified"],
	filters: {
		"is_disabled": 0,
	},
	auto: true,
	cache: "studio-components",
	orderBy: "creation asc",
	pageLength: 50,
})

export { studioComponents }
