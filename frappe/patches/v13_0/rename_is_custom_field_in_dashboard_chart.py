import frappe
from frappe.model.utils.rename_field import rename_field


def execute():
	if not frappe.db.table_exists("Dashboard Chart"):
		return

	frappe.reload_doc("desk", "doctype", "dashboard_chart")

	if frappe.db.has_column("Dashboard Chart", "is_custom"):
		rename_field("Dashboard Chart", "is_custom", "use_report_chart")
