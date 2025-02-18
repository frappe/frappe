import { createListResource } from "frappe-ui"

export const studioVariables = createListResource({
	doctype: "Studio Page Variable",
	parent: "Studio Page",
	fields: ["name", "variable_name", "variable_type", "initial_value", "parent"],
	orderBy: "modified desc",
	pageLength: 50,
})