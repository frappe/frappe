import frappe


def execute() -> None:
	frappe.db.change_column_type("__Auth", column="password", type="TEXT")
