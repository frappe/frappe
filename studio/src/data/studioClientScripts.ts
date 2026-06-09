import { createListResource } from "frappe-ui"

// Junction rows linking a Studio Page to its Studio Client Scripts
export const studioPageClientScripts = createListResource({
	doctype: "Studio Page Client Script",
	parent: "Studio Page",
	fields: ["name", "studio_script", "parent"],
	orderBy: "idx asc",
	pageLength: 50,
})

// The reusable client script docs themselves
export const studioClientScripts = createListResource({
	doctype: "Studio Client Script",
	fields: ["name", "script_name", "script"],
	orderBy: "modified desc",
	pageLength: 50,
})
