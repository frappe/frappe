import frappe


def execute():
	"""migrate studio resource to studio page resource child table"""
	for page_name in frappe.get_all("Studio Page", pluck="name"):
		resources = frappe.get_all(
			"Studio Page Resource",
			filters={"parent": page_name, "studio_resource": ["is", "set"]},
			fields=["studio_resource", "name"],
		)

		if not resources:
			continue

		for resource in resources:
			resource_doc = frappe.get_doc("Studio Resource", resource.studio_resource)

			frappe.db.set_value(
				"Studio Page Resource",
				resource.name,
				{
					"resource_name": resource_doc.resource_name,
					"resource_type": resource_doc.resource_type,
					"fields": resource_doc.fields,
					"filters": resource_doc.filters,
					"limit": resource_doc.limit,
					"document_type": resource_doc.document_type,
					"document_name": resource_doc.document_name,
					"fetch_document_using_filters": resource_doc.fetch_document_using_filters,
					"whitelisted_methods": resource_doc.whitelisted_methods,
					"url": resource_doc.url,
					"method": resource_doc.method,
					"transform_results": resource_doc.transform_results,
					"transform": resource_doc.transform,
				},
			)
