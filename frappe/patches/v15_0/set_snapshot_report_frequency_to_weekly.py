import frappe
from frappe.core.doctype.system_settings.system_settings import snapshot_report_scheduler


def execute():
	if frappe.db.get_single_value("System Settings", "frequency") == "Weekly":
		return

	enable_snapshot_reports = frappe.db.get_single_value("System Settings", "enable_snapshot_reports")
	frappe.db.set_single_value("System Settings", "frequency", "Weekly")

	if enable_snapshot_reports:
		snapshot_report_scheduler(enable=True, frequency="Weekly")
