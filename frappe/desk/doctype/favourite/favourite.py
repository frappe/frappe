# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""A reader's bookmark on a record: one row per user and record, and nothing on the timeline."""

import frappe
from frappe.model.document import Document


class Favourite(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		reference_doctype: DF.Link
		reference_name: DF.DynamicLink
		user: DF.Link
	# end: auto-generated types

	pass


def on_doctype_update():
	# The unique key is what makes two overlapping toggles safe without a row lock.
	frappe.db.add_unique("Favourite", ["user", "reference_doctype", "reference_name"])
	frappe.db.add_index("Favourite", ["reference_doctype", "reference_name"])


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return None

	return f"""`tabFavourite`.`user` = {frappe.db.escape(user)}"""


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return True

	return doc.user == user


@frappe.whitelist()
def toggle_favourite(doctype: str, name: str, add: str | bool = False):
	"""Add or remove the current user's favourite on the given record.

	:param doctype: DocType of the record
	:param name: Name of the record
	:param add: Truthy to add; anything else removes."""
	from frappe.utils.data import sbool

	frappe.has_permission(doctype, "read", doc=name, throw=True)

	key = {"user": frappe.session.user, "reference_doctype": doctype, "reference_name": str(name)}
	if not sbool(add):
		frappe.db.delete("Favourite", key)
		return

	if frappe.db.exists("Favourite", key):
		return
	try:
		frappe.get_doc(doctype="Favourite", **key).insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		# A second click landed between the check and the insert; the row is there.
		pass


def get_favourites(doctype: str, name: str) -> list[dict]:
	"""Who favourited the record, for `get_docinfo`."""
	return frappe.get_all(
		"Favourite",
		fields=["user", "creation"],
		filters={"reference_doctype": doctype, "reference_name": str(name)},
		order_by="creation asc",
	)
