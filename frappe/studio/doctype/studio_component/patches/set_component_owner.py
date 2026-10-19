import frappe

from studio.studio.doctype.studio_component.studio_component import get_components_for_blocks


def execute():
	"""Components made before they belonged to an app join the first app that uses them, standard apps first."""
	pages = frappe.get_all(
		"Studio Page", fields=["studio_app", "blocks", "draft_blocks"], order_by="is_standard desc"
	)
	for page in pages:
		for blocks in (page.blocks, page.draft_blocks):
			for component in get_components_for_blocks(blocks):
				if not component.studio_app:
					frappe.get_doc("Studio Component", component.name).update(
						{"studio_app": page.studio_app}
					).save()
