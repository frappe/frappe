# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""A reader's bookmark on a record, a list or a saved view: one row per user and target, and nothing on the timeline."""

import frappe
from frappe import _
from frappe.model.document import Document

# A list is stored as its DocType record and a saved view as its view row, so these two
# doctypes' rows are never records: read rights come from the list's doctype instead.
LIST = "DocType"
SAVED_VIEW = "Doctype View"
NOT_RECORDS = (LIST, SAVED_VIEW)


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

	no_feed_on_delete = True

	def after_insert(self):
		self.notify_change("add")

	def on_trash(self):
		self.notify_change("delete")

	def notify_change(self, action):
		"""Tell the record's room that its `favourites` bucket changed."""
		frappe.publish_realtime(
			"docinfo_update",
			{"doc": self.as_dict(), "key": "favourites", "action": action},
			doctype=self.reference_doctype,
			docname=self.reference_name,
			after_commit=True,
		)


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
	"""Add or remove the current user's favourite on a record, a list or a saved view; `add` truthy adds."""
	from frappe.utils.data import sbool

	check_read(doctype, name)

	key = {"user": frappe.session.user, "reference_doctype": doctype, "reference_name": str(name)}
	if not sbool(add):
		# A document delete, not a row delete, so `on_trash` announces the change.
		if name := frappe.db.get_value("Favourite", key):
			frappe.delete_doc("Favourite", name, ignore_permissions=True, delete_permanently=True)
		return

	if frappe.db.exists("Favourite", key):
		return
	# A savepoint: on Postgres a failed insert would otherwise abort the whole transaction.
	frappe.db.savepoint("favourite")
	try:
		frappe.get_doc(doctype="Favourite", **key).insert(ignore_permissions=True)
	except frappe.UniqueValidationError:
		# A second click landed between the check and the insert; the row is there.
		frappe.db.rollback(save_point="favourite")


def check_read(doctype: str, name: str):
	"""Refuse unless the person may read what the row points at."""
	if doctype == LIST:
		return check_list_read(name)

	if doctype == SAVED_VIEW:
		view_doctype = frappe.db.get_value(SAVED_VIEW, name, "reference_doctype")
		if not view_doctype:
			raise frappe.DoesNotExistError(_("{0} {1} not found").format(_(SAVED_VIEW), name))
		frappe.has_permission(SAVED_VIEW, "read", doc=name, throw=True)
		return check_list_read(view_doctype)

	frappe.has_permission(doctype, "read", doc=name, throw=True)


def check_list_read(doctype: str):
	if not frappe.db.exists("DocType", doctype):
		raise frappe.DoesNotExistError(_("{0} {1} not found").format(_("DocType"), doctype))
	frappe.has_permission(doctype, "read", throw=True)


def list_favourites(doctype: str) -> dict:
	"""Whether the person starred this doctype's list, and which of its saved views."""
	view = frappe.qb.DocType(SAVED_VIEW)
	favourite = frappe.qb.DocType("Favourite")
	views = frappe.qb.from_(view).select(view.name).where(view.reference_doctype == doctype)
	rows = (
		frappe.qb.from_(favourite)
		.select(favourite.reference_doctype, favourite.reference_name)
		.where(favourite.user == frappe.session.user)
		.where(
			((favourite.reference_doctype == LIST) & (favourite.reference_name == doctype))
			| ((favourite.reference_doctype == SAVED_VIEW) & favourite.reference_name.isin(views))
		)
		.run(as_dict=True)
	)

	return {
		"list": any(row.reference_doctype == LIST for row in rows),
		"views": sorted(row.reference_name for row in rows if row.reference_doctype == SAVED_VIEW),
	}


def get_favourites(doctype: str, name: str) -> list[dict]:
	"""Who favourited the record, for `get_docinfo`."""
	return frappe.get_all(
		"Favourite",
		fields=["user", "creation"],
		filters={"reference_doctype": doctype, "reference_name": str(name)},
		order_by="creation asc",
	)
