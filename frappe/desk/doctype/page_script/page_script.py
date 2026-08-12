# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.app_state import is_module_disabled
from frappe.model.document import Document

PAGE_SCRIPT_VIEWS = ("Record",)
PAGE_SCRIPT_CHANGED = "page_script_changed"


class PageScript(Document):
	def on_update(self):
		self.notify_change()

	def on_trash(self):
		self.notify_change()

	# Broadcast, not per-user: every mounted page of this doctype replays the tier,
	# and the payload names the doctype only — never the script text.
	def notify_change(self):
		frappe.publish_realtime(
			PAGE_SCRIPT_CHANGED, {"dt": self.dt, "view": self.view}, after_commit=True
		)


@frappe.whitelist()
def get_page_scripts(dt: str, view: str = "Record"):
	"""Return the scripts a Record page of `dt` runs, in run order (creation asc)."""
	# Belt and braces: the whitelist decorator already rejects a non-str `dt`, and
	# one reaching get_all would be a filter operator (`["!=", ""]`) that reads
	# every doctype's scripts past the permission check below.
	if not isinstance(dt, str):
		frappe.throw(_("Document Type must be a name"))
	if view not in PAGE_SCRIPT_VIEWS:
		frappe.throw(_("Invalid Page Script view: {0}").format(view))
	# Reading the doctype is the gate: whoever may open the record receives its
	# scripts, exactly as desk ships `__custom_js` inside meta.
	frappe.has_permission(dt, "read", throw=True)

	rows = frappe.get_all(
		"Page Script",
		filters={"dt": dt, "view": view, "enabled": 1},
		fields=["name", "script", "module"],
		order_by="creation asc",
	)
	return {
		"scripts": [
			{"name": row.name, "script": row.script or ""}
			for row in rows
			if not is_module_disabled(row.module)
		],
		"can_write": bool(frappe.has_permission("Page Script", "write")),
	}
