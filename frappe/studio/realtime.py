import frappe
from frappe.realtime import get_site_room


def publish_doc_change(doctype: str, name: str, studio_app: str | None = None):
	if frappe.flags.in_migrate or frappe.flags.in_install or frappe.flags.in_patch:
		return

	frappe.publish_realtime(
		"studio_doc_update",
		{
			"doctype": doctype,
			"name": name,
			"studio_app": studio_app,
			"source": "disk" if frappe.flags.in_import else "save",
		},
		room=get_site_room(),
		after_commit=True,
	)
