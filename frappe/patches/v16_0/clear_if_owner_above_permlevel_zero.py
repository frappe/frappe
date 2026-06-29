import frappe


def execute():
	# `if_owner` is only honoured at permlevel 0; normalise existing rows above that level.
	for doctype in ("DocPerm", "Custom DocPerm"):
		rows = frappe.get_all(
			doctype,
			filters={"permlevel": [">", 0], "if_owner": 1},
			fields=["name", "parent", "role", "permlevel"],
		)
		for row in rows:
			twin = frappe.db.exists(
				doctype,
				{"parent": row.parent, "role": row.role, "permlevel": row.permlevel, "if_owner": 0},
			)
			if twin:
				frappe.db.delete(doctype, {"name": row.name})
			else:
				frappe.db.set_value(doctype, row.name, "if_owner", 0, update_modified=False)
