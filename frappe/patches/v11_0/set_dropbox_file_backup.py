import frappe
from frappe.utils import cint


def execute():
	frappe.reload_doctype("Dropbox Settings")
	check_dropbox_enabled = cint(frappe.db.get_single_value("Dropbox Settings", "enabled"))
	if check_dropbox_enabled == 1:
		frappe.db.set_single_value("Dropbox Settings", "file_backup", 1)
