import frappe


def execute():
	"""update global utility usage"""
	StudioPage = frappe.qb.DocType("Studio Page")
	pages = (
		frappe.qb.from_(StudioPage)
		.select(StudioPage.name, StudioPage.blocks, StudioPage.draft_blocks)
		.where(
			(StudioPage.blocks.like("%studio.call%"))
			| (StudioPage.draft_blocks.like("%studio.call%"))
			| (StudioPage.blocks.like("%studio.navigate%"))
			| (StudioPage.draft_blocks.like("%studio.navigate%"))
		)
	).run(as_dict=True)

	for page in pages:
		updates = {}
		blocks = page.get("blocks")
		draft_blocks = page.get("draft_blocks")

		if blocks:
			updates["blocks"] = blocks.replace("studio.call", "call").replace(
				"studio.navigate", "router.push"
			)

		if draft_blocks:
			updates["draft_blocks"] = draft_blocks.replace("studio.call", "call").replace(
				"studio.navigate", "router.push"
			)

		frappe.db.set_value("Studio Page", page.name, updates, update_modified=False)
