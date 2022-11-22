import frappe
from frappe.utils import cint


def execute():
	expiry_period = (
		cint(frappe.db.get_single_value("System Settings", "prepared_report_expiry_period")) or 30
	)
	frappe.get_single("Log Settings").register_doctype("Prepared Report", expiry_period)

	singles = frappe.qb.DocType("Singles")
	frappe.qb.from_(singles).delete().where(
		(singles.doctype == "System Settings")
		& (singles.field.isin(["enable_prepared_report_auto_deletion", "prepared_report_expiry_period"]))
	).run()
