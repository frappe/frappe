import frappe
from frappe.model.rename_doc import rename_doc


def execute():
	"""Rename the site's triggers named `<app>/<title>`, the form of the triggers apps ship."""
	for name in frappe.get_all("Flow Trigger", {"name": ["like", "%/%"]}, pluck="name"):
		new = base = name.replace("/", "-")
		count = 1
		while frappe.db.exists("Flow Trigger", new):
			count += 1
			new = f"{base}-{count}"
		rename_doc(
			"Flow Trigger", name, new, force=True, validate=False, show_alert=False, rebuild_search=False
		)
