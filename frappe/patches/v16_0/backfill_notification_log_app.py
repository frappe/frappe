from collections import defaultdict

import frappe
from frappe.modules.utils import get_doctype_app_map


def execute():
	"""Backfill Notification Log.app from the reference document's owning app.

	The `app` column scopes app-specific notification panels. New rows get it set in
	NotificationLog.before_insert; this seeds existing rows. Rows whose document_type has no
	resolvable app (or no document_type at all) are left empty on purpose — they remain
	global-only, matching the pre-`app` behaviour.
	"""
	frappe.reload_doctype("Notification Log")

	app_doctypes: dict[str, list[str]] = defaultdict(list)
	for doctype, app in get_doctype_app_map().items():
		if app:
			app_doctypes[app].append(doctype)

	for app, doctypes in app_doctypes.items():
		frappe.db.set_value(
			"Notification Log",
			{"document_type": ["in", doctypes], "app": ["in", [None, ""]]},
			"app",
			app,
			update_modified=False,
		)
