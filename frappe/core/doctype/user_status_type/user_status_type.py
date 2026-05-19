# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.model.document import Document

MASTER_STATUSES = (
	"Available",
	"Away",
	"Busy",
	"Do Not Disturb",
	"Out of Office",
	"Invisible",
)

DEFAULT_USER_STATUS_TYPES = (
	# (label, master_status, icon, description)
	("Available", "Available", "check-circle", "Reachable and available to chat."),
	("Away", "Away", "clock", "Stepped away from the desk."),
	("Busy", "Busy", "circle-dot", "Heads down — please ping only if urgent."),
	("Do Not Disturb", "Do Not Disturb", "circle-slash", "Notifications muted."),
	("Out of Office", "Out of Office", "plane", "Not at work today."),
	("Invisible", "Invisible", "circle-off", "Appears offline to other users."),
)


class UserStatusType(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		enabled: DF.Check
		icon: DF.Data | None
		master_status: DF.Literal["Available", "Away", "Busy", "Do Not Disturb", "Out of Office", "Invisible"]
		status_label: DF.Data
	# end: auto-generated types

	def validate(self):
		if self.master_status not in MASTER_STATUSES:
			frappe.throw(_("Master Status must be one of: {0}").format(", ".join(MASTER_STATUSES)))

	def on_update(self):
		# A type's master_status or enabled flag changing can invalidate every
		# user that has this type set. Types change rarely; wipe the namespace.
		frappe.cache.delete_keys("user_status:")

	def on_trash(self):
		# Block deletion if any user still references this type — protects the
		# add_user_info JOIN from null masters with non-null status names.
		users = frappe.db.count("User", {"user_status": self.name})
		if users:
			frappe.throw(
				_(
					"Cannot delete: {0} user(s) currently have this status. Clear or change their status first."
				).format(users)
			)
		frappe.cache.delete_keys("user_status:")


def ensure_user_status_type(
	label: str,
	master: str,
	icon: str | None = None,
	description: str | None = None,
	enabled: bool = True,
) -> str:
	"""Idempotent installer for a User Status Type.

	Apps call this from their ``after_install`` (and ideally
	``after_app_install``) hook to register their statuses. Re-running is
	safe: an existing row is updated to match the supplied master/icon/
	description rather than inserted twice.
	"""
	if master not in MASTER_STATUSES:
		frappe.throw(_("Master Status must be one of: {0}").format(", ".join(MASTER_STATUSES)))

	if frappe.db.exists("User Status Type", label):
		doc = frappe.get_doc("User Status Type", label)
		dirty = False
		for fieldname, value in (
			("master_status", master),
			("icon", icon),
			("description", description),
			("enabled", 1 if enabled else 0),
		):
			if value is None and fieldname in ("icon", "description"):
				continue
			if doc.get(fieldname) != value:
				doc.set(fieldname, value)
				dirty = True
		if dirty:
			doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc(
		{
			"doctype": "User Status Type",
			"status_label": label,
			"master_status": master,
			"icon": icon,
			"description": description,
			"enabled": 1 if enabled else 0,
		}
	).insert(ignore_permissions=True)
	return doc.name


def seed_default_user_status_types() -> None:
	"""Create the six standard User Status Type rows. Idempotent."""
	for label, master, icon, description in DEFAULT_USER_STATUS_TYPES:
		ensure_user_status_type(label, master, icon=icon, description=description)


@frappe.whitelist()
def get_status_types_for_picker() -> list[dict]:
	"""Return enabled User Status Types grouped by master, for the picker UI."""
	rows = frappe.get_all(
		"User Status Type",
		filters={"enabled": 1},
		fields=["name", "status_label", "master_status", "icon", "description"],
		order_by="master_status asc, status_label asc",
	)
	return [
		{
			"name": r.name,
			"label": r.status_label,
			"master": r.master_status,
			"icon": r.icon,
			"description": r.description,
		}
		for r in rows
	]
