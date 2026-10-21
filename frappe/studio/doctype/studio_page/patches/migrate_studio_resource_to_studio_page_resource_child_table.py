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
			StudioResource = frappe.qb.DocType("Studio Resource")
			studio_resource = (
				frappe.qb.from_(StudioResource)
				.select(
					StudioResource.resource_name,
					StudioResource.resource_type,
					StudioResource.fields,
					StudioResource.filters,
					StudioResource.limit,
					StudioResource.document_type,
					StudioResource.document_name,
					StudioResource.fetch_document_using_filters,
					StudioResource.whitelisted_methods,
					StudioResource.url,
					StudioResource.method,
					StudioResource.transform_results,
					StudioResource.transform,
				)
				.where(StudioResource.name == resource.studio_resource)
				.run(as_dict=True)
			)

			if studio_resource:
				studio_resource = studio_resource[0]

			frappe.db.set_value(
				"Studio Page Resource",
				resource.name,
				{
					"resource_name": studio_resource.resource_name,
					"resource_type": studio_resource.resource_type,
					"fields": studio_resource.fields,
					"filters": studio_resource.filters,
					"limit": studio_resource.limit,
					"document_type": studio_resource.document_type,
					"document_name": studio_resource.document_name,
					"fetch_document_using_filters": studio_resource.fetch_document_using_filters,
					"whitelisted_methods": studio_resource.whitelisted_methods,
					"url": studio_resource.url,
					"method": studio_resource.method,
					"transform_results": studio_resource.transform_results,
					"transform": studio_resource.transform,
				},
			)
