import frappe


def execute():
	"""
	Removes direct references to the frappeUI namespace
	The editor doesn't import the entire module anymore, instead, relies on resolveComponent to find the component
	"""
	pages = frappe.get_all(
		"Studio Page",
		or_filters={
			"blocks": ["like", "%frappeUI.%"],
			"draft_blocks": ["like", "%frappeUI.%"],
		},
		fields=["name", "blocks", "draft_blocks"],
	)
	for page in pages:
		updates = {}
		blocks = page.get("blocks")
		draft_blocks = page.get("draft_blocks")

		if blocks and "frappeUI." in blocks:
			updates["blocks"] = blocks.replace("frappeUI.", "")

		if draft_blocks and "frappeUI." in draft_blocks:
			updates["draft_blocks"] = draft_blocks.replace("frappeUI.", "")

		frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)
