import frappe
from frappe.cache_manager import clear_defaults_cache


def execute():
	frappe.db.set_default(
		"hold_queue",
		frappe.db.get_default("hold_queue", "Administrator") or 0,
		parent="__default",
	)

	frappe.db.delete(
		"DefaultValue",
		{
			"defkey": "hold_queue",
			"parent": ("!=", "__default"),
		},
	)

	clear_defaults_cache()
