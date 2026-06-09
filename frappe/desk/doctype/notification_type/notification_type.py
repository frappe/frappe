# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.caching import http_cache

# Built-in notification types shipped by the framework. These mirror the values
# that `Notification Log.type` historically used as a Select, so the Select -> Link
# conversion is value-compatible. They are seeded in code (like Gender / Salutation)
# and protected from deletion below.
BUILTIN_NOTIFICATION_TYPES = [
	{"type_name": "Mention", "icon": "at-sign", "color": "blue"},
	{"type_name": "Energy Point", "icon": "award", "color": "yellow"},
	{"type_name": "Assignment", "icon": "user-check", "color": "green"},
	{"type_name": "Share", "icon": "share-2", "color": "blue"},
	{"type_name": "Alert", "icon": "alert-circle", "color": "orange"},
]
BUILTIN_TYPE_NAMES = frozenset(d["type_name"] for d in BUILTIN_NOTIFICATION_TYPES)


class NotificationType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		color: DF.Data | None
		enabled: DF.Check
		icon: DF.Data | None
		type_name: DF.Data
	# end: auto-generated types

	def on_trash(self):
		# protect framework-shipped types from deletion (but allow it during
		# migrations/patches so the doctype can be reorganised if ever needed)
		if (
			self.name in BUILTIN_TYPE_NAMES
			and not frappe.flags.in_migrate
			and not frappe.flags.in_patch
		):
			frappe.throw(
				_("{0} is a built-in Notification Type and cannot be deleted. Disable it instead.").format(
					frappe.bold(self.name)
				)
			)


def install_notification_types():
	"""Idempotently create the framework's built-in Notification Types.

	Invoked from `after_install` and `after_migrate`. Existing records are left
	untouched so site-level customisation (e.g. disabling) is preserved.
	"""
	for definition in BUILTIN_NOTIFICATION_TYPES:
		if frappe.db.exists("Notification Type", definition["type_name"]):
			continue

		doc = frappe.new_doc("Notification Type")
		doc.update(definition)
		doc.insert(ignore_permissions=True)


@frappe.whitelist()
@http_cache(max_age=300, stale_while_revalidate=60 * 60)
def get_notification_types():
	"""Return rendering metadata for the notification panel component."""
	return frappe.get_all(
		"Notification Type",
		filters={"enabled": 1},
		fields=["name", "type_name", "icon", "color"],
	)
