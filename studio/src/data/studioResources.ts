import { createListResource } from "frappe-ui"

export const studioPageResources = createListResource({
	doctype: "Studio Page Resource",
	parent: "Studio Page",
	fields: [
		"resource_type",
		"resource_name",
		"fields",
		"filters",
		"limit",
		"document_type",
		"document_name",
		"fetch_document_using_filters",
		"url",
		"method",
		"whitelisted_methods",
		"transform_results",
		"transform",
		"name as resource_id",
	],
})
