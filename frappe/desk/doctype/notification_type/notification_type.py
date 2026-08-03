# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils.caching import http_cache

# Built-in notification types shipped by the framework. These mirror the values
# that `Notification Log.type` historically used as a Select, so the Select -> Link
# conversion is value-compatible. They are seeded in code (like Gender / Salutation)
# and protected from deletion below. Notification Type is purely categorical — any
# presentation (icon/avatar) is owned by the consuming UI, not stored here.
BUILTIN_NOTIFICATION_TYPES = [
	{"type_name": "Mention"},
	{"type_name": "Energy Point"},
	{"type_name": "Assignment"},
	{"type_name": "Share"},
	{"type_name": "Alert"},
]
BUILTIN_TYPE_NAMES = frozenset(d["type_name"] for d in BUILTIN_NOTIFICATION_TYPES)


class NotificationType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		type_name: DF.Data
	# end: auto-generated types

	def on_trash(self):
		# protect framework-shipped types from deletion (but allow it during
		# migrations/patches so the doctype can be reorganised if ever needed)
		if self.name in BUILTIN_TYPE_NAMES and not frappe.flags.in_migrate and not frappe.flags.in_patch:
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
	"""Return the enabled notification types (categorical only — no presentation).

	Hosts use this to build type tabs / filters in the notification panel.
	"""
	return frappe.get_all(
		"Notification Type",
		filters={"enabled": 1},
		fields=["name", "type_name", "enabled"],
	)


@frappe.whitelist()
def enable_email_for_all_users(notification_type: str):
	"""Opt-in mass action: seed this type into every user's email preferences.

	New types are opt-in by default; this is the explicit, deliberate way to turn a
	type on for everyone (e.g. from the form's Actions menu).
	"""
	from frappe.desk.doctype.notification_log.notification_log import get_skip_email_types

	frappe.only_for("System Manager")

	if not frappe.db.exists("Notification Type", notification_type):
		frappe.throw(_("{0} does not exist").format(frappe.bold(notification_type)))

	if not frappe.db.get_value("Notification Type", notification_type, "enabled"):
		frappe.throw(_("Enable the notification type before emailing it to users."))

	if notification_type in get_skip_email_types():
		frappe.throw(_("{0} never sends email, so it cannot be enabled for users.").format(notification_type))

	frappe.enqueue(
		"frappe.desk.doctype.notification_type.notification_type.seed_type_into_settings",
		notification_type=notification_type,
		enqueue_after_commit=True,
	)
	frappe.msgprint(
		_("Enabling email for {0} across all users in the background.").format(
			frappe.bold(notification_type)
		),
		alert=True,
	)


def seed_type_into_settings(notification_type: str):
	"""Append `notification_type` to every Notification Settings that doesn't have it yet."""
	if not frappe.db.exists("Notification Type", notification_type):
		return

	settings_names = frappe.get_all("Notification Settings", pluck="name")
	for name in settings_names:
		exists = frappe.db.exists(
			"Notification Type Preference",
			{"parent": name, "notification_type": notification_type},
		)
		if exists:
			continue
		settings = frappe.get_doc("Notification Settings", name)
		settings.append("email_notification_types", {"notification_type": notification_type})
		settings.save(ignore_permissions=True)
