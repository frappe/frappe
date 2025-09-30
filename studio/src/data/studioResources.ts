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
		"sort_field",
		"sort_order",
		"document_type",
		"document_name",
		"fetch_document_using_filters",
		"url",
		"method",
		"params",
		"whitelisted_methods",
		"transform_results",
		"transform",
		"name as resource_id",
	],
})
