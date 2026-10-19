import { createListResource } from "frappe-ui"

const studioComponents = createListResource({
	method: "GET",
	doctype: "Studio Component",
	fields: ["component_id", "component_name", "creation", "modified"],
	// loaded per app by the studio store
	filters: {
		"is_disabled": 0,
	},
	cache: "studio-components",
	orderBy: "creation asc",
	pageLength: 50,
})

export { studioComponents }
