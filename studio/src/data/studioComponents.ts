import { createListResource } from "frappe-ui"

const studioComponents = createListResource({
	method: "GET",
	doctype: "Studio Component",
	fields: ["component_id", "component_name", "blocks", "creation", "modified"],
	auto: true,
	cache: "studio-components",
	orderBy: "creation asc",
	pageLength: 50,
})

export { studioComponents }
