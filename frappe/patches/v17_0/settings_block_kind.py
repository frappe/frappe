import frappe


def execute():
	"""Move the Settings Block rows a site holds in the old shape to the new one.

	A shipped record is imported again from its file, which `before_import` reads in either shape;
	this is for the rows the files do not replace.
	"""
	block = frappe.qb.DocType("Settings Block")
	blank = lambda column: column.isnull() | (column == "")  # noqa: E731
	component = ~blank(block.component)

	(
		frappe.qb.update(block)
		.set(block.saves_fields, block.fields)
		.set(block.fields, None)
		.where(component & blank(block.saves_fields))
		.run()
	)
	frappe.qb.update(block).set(block.kind, "Component").where(component).run()

	if frappe.db.has_column("Settings Block", "settings"):
		old = frappe.qb.Field("settings", table=block)
		frappe.qb.update(block).set(block.search_entries, old).where(
			~blank(old) & blank(block.search_entries)
		).run()
