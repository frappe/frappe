import frappe


def execute():
	# `if_owner` is only honoured at permlevel 0; clear it above that level, folding flags into
	# an already-cleared sibling so no access is lost before dropping the redundant row.
	for doctype in ("DocPerm", "Custom DocPerm"):
		flags = [
			df.fieldname
			for df in frappe.get_meta(doctype).fields
			if df.fieldtype == "Check" and df.fieldname != "if_owner"
		]

		rows = frappe.get_all(
			doctype,
			filters={"permlevel": [">", 0], "if_owner": 1},
			fields=["name", "parent", "role", "permlevel", *flags],
		)

		for row in rows:
			twin = frappe.db.get_value(
				doctype,
				{"parent": row.parent, "role": row.role, "permlevel": row.permlevel, "if_owner": 0},
				["name", *flags],
				as_dict=True,
			)
			if not twin:
				frappe.db.set_value(doctype, row.name, "if_owner", 0, update_modified=False)
				continue

			gained = {flag: 1 for flag in flags if row.get(flag) and not twin.get(flag)}
			if gained:
				frappe.db.set_value(doctype, twin.name, gained, update_modified=False)
			frappe.db.delete(doctype, {"name": row.name})
