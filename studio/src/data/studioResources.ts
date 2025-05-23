import { createListResource } from "frappe-ui"

const studioResources = createListResource({
	method: "GET",
	doctype: "Studio Resource",
	fields: ["name", "resource_type", "fields", "document_type", "document_name", "url", "method"],
	auto: true,
	cache: "resources",
	orderBy: "modified desc",
	pageLength: 50,
})

const studioPageResources = createListResource({
	doctype: "Studio Page Resource",
	parent: "Studio Page",
	fields: [
		"studio_resource.resource_type",
		"studio_resource.fields",
		"studio_resource.filters",
		"studio_resource.limit",
		"studio_resource.document_type",
		"studio_resource.document_name",
		"studio_resource.fetch_document_using_filters",
		"studio_resource.url",
		"studio_resource.method",
		"studio_resource.whitelisted_methods",
		"studio_resource.name as resource_id",
		"studio_resource.resource_name",
		"studio_resource.transform_results",
		"studio_resource.transform",
		"name",
	],
})

export { studioResources, studioPageResources }
