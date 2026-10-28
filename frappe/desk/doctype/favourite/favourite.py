# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""A reader's bookmark on a record, a list or a saved view: one row per user and target, and nothing on the timeline."""

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.query_builder.functions import Lower

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


@frappe.desk_v2_only
@frappe.whitelist()
def toggle_favourite(doctype: str, name: str, add: str | bool = False):
	"""Add or remove the current user's favourite on a record, a list or a saved view; `add` truthy adds."""
	from frappe.utils.data import sbool

	name = readable_target(doctype, name)

	key = {"user": frappe.session.user, "reference_doctype": doctype, "reference_name": name}
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


def readable_target(doctype: str, name: str) -> str:
	"""The name to store for what the row points at; refuses unless the person may read it."""
	if doctype == LIST:
		return readable_list(name)

	if doctype == SAVED_VIEW:
		frappe.has_permission(SAVED_VIEW, "read", doc=name, throw=True)
		readable_list(frappe.db.get_value(SAVED_VIEW, name, "reference_doctype"))
		return str(name)

	frappe.has_permission(doctype, "read", doc=name, throw=True)
	return str(name)


def readable_list(doctype: str) -> str:
	"""The doctype's own spelling of its name, so a list has one row whatever case the caller sent."""
	stored = frappe.db.get_value("DocType", doctype) or doctype_in_any_case(doctype)
	if not stored:
		raise frappe.DoesNotExistError(_("{0} {1} not found").format(_("DocType"), doctype))
	if not may_read_list(stored):
		frappe.throw(_("You are not permitted to read {0}.").format(_(stored)), frappe.PermissionError)
	return stored


def doctype_in_any_case(doctype: str | None) -> str | None:
	"""The DocType named `doctype` in another case, on Postgres, whose name lookup does not ignore case."""
	if not doctype or frappe.db.db_type != "postgres":
		return None
	table = frappe.qb.DocType("DocType")
	names = (
		frappe.qb.from_(table)
		.select(table.name)
		.where(Lower(table.name) == doctype.lower())
		.limit(1)
		.run(pluck=True)
	)
	return names[0] if names else None


def may_read_list(doctype: str) -> bool:
	"""A list's read check: `read` on its doctype, never on the `DocType` record most people cannot read."""
	return bool(frappe.has_permission(doctype, "read"))


def readable_views(names: list[str]) -> dict[str, frappe._dict]:
	"""`{name: view}` of the saved views the person may read, on a list they may read; one query."""
	if not names:
		return {}
	# `get_list` applies the view's own read rule (its permission query), so this is the toggle's check in bulk.
	views = frappe.get_list(
		SAVED_VIEW,
		filters={"name": ("in", names)},
		fields=["name", "label", "reference_doctype"],
		limit_page_length=0,
	)
	return {view.name: view for view in views if may_read_list(view.reference_doctype)}


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
