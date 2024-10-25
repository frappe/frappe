import frappe


def execute() -> None:
	singles = frappe.qb.Table("tabSingles")
	frappe.qb.from_(singles).delete().where(
		(singles.doctype == "System Settings") & (singles.field == "is_first_startup")
	).run()
