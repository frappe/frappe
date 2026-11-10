import frappe


def execute():
	"""Keep the charts that upgrading sites already have. Fresh installs skip patches, so they get the new charts.

	A site that has not finished the setup wizard has no charts of its own yet, so it stays on the new
	charts like a fresh install.

	`set_single_value` alone does not reach `frappe.boot.sysdefaults`, which desk reads the flag from.
	"""
	if not frappe.is_setup_complete():
		return

	frappe.db.set_single_value("System Settings", "use_classic_charts", 1)
	frappe.db.set_default("use_classic_charts", 1)
