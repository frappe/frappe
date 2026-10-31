# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""A reader's bookmark on a record, a list or a saved view: one row per user and target, and nothing on the timeline."""

import frappe
from frappe import _
from frappe.desk.doctype.doctype_view.key_space import KeySpace, find_views
from frappe.model.document import Document
from frappe.query_builder.functions import Lower

# A list, and each of its saved views by `view`, is stored as the list's DocType record, which
# is never a record here: read rights come from the list's doctype instead.
LIST = "DocType"
PLAIN_LIST = ""


class Favourite(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		reference_doctype: DF.Link
		reference_name: DF.DynamicLink
		user: DF.Link
		view: DF.Data
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
	frappe.db.add_unique("Favourite", ["user", "reference_doctype", "reference_name", "view"])
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
def toggle_favourite(doctype: str, name: str, add: str | bool = False, view: str | None = None):
	"""Add or remove the current user's favourite on a record, a list, or the list's saved view `view`; `add` truthy adds."""
	from frappe.utils.data import sbool

	view = view or PLAIN_LIST
	name = readable_target(doctype, name, view)

	key = {"user": frappe.session.user, "reference_doctype": doctype, "reference_name": name, "view": view}
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


def readable_target(doctype: str, name: str, view: str = PLAIN_LIST) -> str:
	"""The name to store for what the row points at; refuses unless the person may read it."""
	if doctype == LIST:
		stored = readable_list(name)
		if view and not KeySpace(stored).find(view):
			raise frappe.DoesNotExistError(_("This view doesn't exist."))
		return stored

	if view:
		frappe.throw(_("Only a list has saved views."))

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


def readable_views(targets: list[tuple[str, str]]) -> dict[tuple[str, str], frappe._dict]:
	"""`{(doctype, key): view}` of the saved views the person sees, on a list they may read; the toggle's check in bulk."""
	views = find_views(targets)
	return {target: view for target, view in views.items() if may_read_list(target[0])}


def list_favourites(doctype: str) -> dict:
	"""Whether the person starred this doctype's list, and the keys of the saved views they starred."""
	views = frappe.get_all(
		"Favourite",
		filters={"user": frappe.session.user, "reference_doctype": LIST, "reference_name": doctype},
		pluck="view",
	)

	return {"list": PLAIN_LIST in views, "views": sorted(view for view in views if view != PLAIN_LIST)}


def get_favourites(doctype: str, name: str) -> list[dict]:
	"""Who favourited the record, for `get_docinfo`."""
	return frappe.get_all(
		"Favourite",
		fields=["user", "creation"],
		filters={"reference_doctype": doctype, "reference_name": str(name), "view": PLAIN_LIST},
		order_by="creation asc",
	)
