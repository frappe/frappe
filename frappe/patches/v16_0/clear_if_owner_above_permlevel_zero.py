import frappe


def execute():
	# `if_owner` is only honoured at permlevel 0; clear it on existing rows above that level.
	for doctype in ("DocPerm", "Custom DocPerm"):
		table = frappe.qb.DocType(doctype)
		frappe.qb.update(table).set(table.if_owner, 0).where(
			(table.permlevel > 0) & (table.if_owner == 1)
		).run()
