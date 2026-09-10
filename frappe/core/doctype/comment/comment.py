# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe.database.schema import add_column
from frappe.desk.notifications import notify_mentions
from frappe.exceptions import ImplicitCommitError
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read, has_controller_permissions
from frappe.website.utils import clear_cache


class Comment(Document):
	_DOCTYPE_NAME = "Comment"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		comment_by: DF.Data | None
		comment_email: DF.Data | None
		comment_type: DF.Literal[
			"Comment",
			"Like",
			"Info",
			"Label",
			"Workflow",
			"Created",
			"Submitted",
			"Cancelled",
			"Updated",
			"Deleted",
			"Assigned",
			"Assignment Completed",
			"Attachment",
			"Attachment Removed",
			"Shared",
			"Unshared",
			"Bot",
			"Relinked",
			"Edit",
		]
		content: DF.HTMLEditor | None
		ip_address: DF.Data | None
		published: DF.Check
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		reference_owner: DF.Data | None
		seen: DF.Check
		subject: DF.Text | None
	# end: auto-generated types

	no_feed_on_delete = True

	def after_insert(self):
		notify_mentions(
			self.reference_doctype,
			self.reference_name,
			self.content,
			source_doctype=self.doctype,
			source_name=self.name,
		)
		self.refresh_count()
		self.notify_change("add")

	def validate(self):
		if not self.comment_email:
			self.comment_email = frappe.session.user
		self.content = frappe.utils.sanitize_html(
			self.content, always_sanitize=True, disallowed_tags=["form", "input", "button"]
		)

	def on_update(self):
		old_doc = self.get_doc_before_save()
		if old_doc and (old_doc.reference_doctype, old_doc.reference_name) != (
			self.reference_doctype,
			self.reference_name,
		):
			self.refresh_count(old_doc.reference_doctype, old_doc.reference_name)
			self.refresh_count()

		if not self.is_new():
			self.notify_change("update")

	def on_trash(self):
		self.notify_change("delete")

	def after_delete(self):
		# after the row is gone, so the recount does not include it
		self.refresh_count()

	def refresh_count(self, reference_doctype=None, reference_name=None):
		if self.comment_type == "Comment":
			refresh_comment_count(
				reference_doctype or self.reference_doctype, reference_name or self.reference_name
			)

	def notify_change(self, action):
		key_map = {
			"Like": "like_logs",
			"Assigned": "assignment_logs",
			"Assignment Completed": "assignment_logs",
			"Comment": "comments",
			"Attachment": "attachment_logs",
			"Attachment Removed": "attachment_logs",
		}
		key = key_map.get(self.comment_type)
		if not key:
			return

		frappe.publish_realtime(
			"docinfo_update",
			{"doc": self.as_dict(), "key": key, "action": action},
			doctype=self.reference_doctype,
			docname=self.reference_name,
			after_commit=True,
		)


def on_doctype_update():
	frappe.db.add_index("Comment", ["reference_doctype", "reference_name"])


MAX_COMMENT_CHAIN_DEPTH = 10
# a comment's reference can be another Comment, so read access comes from the real
# document at the end of the chain: Comment -> Comment -> ToDo checks read on the ToDo.
# a chain that never reaches a document is refused


def has_permission(doc, ptype="read", user=None, debug=False):
	"""A comment is readable as far as the document it was written on is."""
	if ptype != "read":
		return True

	reference_doctype, reference_name = doc.reference_doctype, doc.reference_name
	seen = {doc.name}

	for _ in range(MAX_COMMENT_CHAIN_DEPTH):
		if not (reference_doctype and reference_name):
			return True

		if reference_doctype != "Comment":
			return frappe.has_permission(
				reference_doctype, ptype="read", doc=reference_name, user=user, debug=debug
			)

		if reference_name in seen:
			break
		seen.add(reference_name)

		reference = frappe.db.get_value("Comment", reference_name, ["reference_doctype", "reference_name"])
		if reference is None:
			break
		reference_doctype, reference_name = reference

	return False


def get_permission_query_conditions(user: str | None = None) -> str:
	"""Drop comments on doctypes the user cannot read at all.

	Per-document access is `has_permission`'s job; it is not one condition on `tabComment`.
	"""
	user = user or frappe.session.user
	if user == "Administrator":
		return ""

	unreferenced = "`tabComment`.`reference_doctype` IS NULL OR `tabComment`.`reference_doctype` = ''"

	readable_doctypes = ", ".join(repr(dt) for dt in get_doctypes_with_read(user))
	if not readable_doctypes:
		return f"({unreferenced})"

	return f"({unreferenced} OR `tabComment`.`reference_doctype` IN ({readable_doctypes}))"


def get_document_comments(
	reference_doctype: str,
	reference_name: str | int,
	fields: list[str],
	comment_types: list[str] | None = None,
	extra_filters: list | None = None,
	user: str | None = None,
	**kwargs,
) -> list[frappe._dict]:
	"""Read a document's comment rows, honouring the Comment `has_permission` hooks.

	The caller must have checked read on the document. Pass `user` to compose for someone
	other than the session user, as the follow digests do. Hooks decide per comment type and
	are handed the reference and the type only, so one reading any other field sees nothing.
	"""
	filters = [
		["reference_doctype", "=", reference_doctype],
		["reference_name", "=", reference_name],
		*(extra_filters or []),
	]

	if comment_types is None:
		comment_types = frappe.get_all("Comment", filters=filters, pluck="comment_type", distinct=True)

	def permitted(comment_type: str) -> bool:
		probe = frappe._dict(
			doctype="Comment",
			name=None,
			reference_doctype=reference_doctype,
			reference_name=reference_name,
			comment_type=comment_type,
		)
		return has_controller_permissions(probe, "read", user=user)

	if not (allowed := [comment_type for comment_type in comment_types if permitted(comment_type)]):
		return []

	filters.append(["comment_type", "in", allowed])
	return frappe.get_all("Comment", fields=fields, filters=filters, **kwargs)


def refresh_comment_count(reference_doctype, reference_name):
	"""Recount comments and communications on the referenced document into `_comment_count`."""
	if not reference_doctype or not reference_name:
		return

	# get_meta raises for an unknown doctype, so the table name below is always a real one
	meta = frappe.get_meta(reference_doctype)
	if meta.issingle or meta.get("is_virtual"):
		return

	reference = {"reference_doctype": reference_doctype, "reference_name": reference_name}
	count = frappe.db.count("Comment", reference | {"comment_type": "Comment"}) + frappe.db.count(
		"Communication", reference
	)

	try:
		# use sql, so that we do not mess with the timestamp
		frappe.db.sql(
			f"""update `tab{reference_doctype}` set `_comment_count`=%s where name=%s""",  # nosec
			(count, reference_name),
		)
	except Exception as e:
		if frappe.db.is_missing_column(e) and getattr(frappe.local, "request", None):
			pass
		else:
			raise
	else:
		if frappe.flags.in_patch:
			return

		if route := frappe.get_cached_value(reference_doctype, reference_name, "route"):
			clear_cache(route)
