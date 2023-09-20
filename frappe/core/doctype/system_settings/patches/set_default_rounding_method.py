import frappe
from frappe.database.database import savepoint


def execute():
	"""set default rounding method"""

	with savepoint(Exception):
		settings = frappe.get_doc("System Settings")
		settings.rounding_method = "Banker's Rounding (legacy)"
		settings.flag.ignore_mandatory = True
		settings.save(ignore_version=True)
