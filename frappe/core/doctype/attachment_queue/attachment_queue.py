# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

from pathlib import Path

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read
from frappe.utils import add_to_date, cint, cstr, now

SUPPORTED_EXTENSIONS = (".pdf", ".jpeg", ".jpg", ".png")


class AttachmentQueue(Document):
	"""An uploaded file waiting to be written into a document."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		created_document: DF.DynamicLink | None
		document_type: DF.Link
		source_file: DF.Attach
	# end: auto-generated types

	def validate(self):
		if self.document_type:
			self.validate_document_type()

		if self.source_file:
			self.validate_source_file_type()

	def validate_document_type(self):
		if not frappe.get_meta(self.document_type).get("enable_upload_first_workflow"):
			frappe.throw(
				_("{0} does not allow document creation from an uploaded file.").format(
					frappe.bold(_(self.document_type))
				),
				title=_("Not Enabled"),
			)

	def validate_source_file_type(self):
		if get_file_extension(self.source_file) not in SUPPORTED_EXTENSIONS:
			frappe.throw(
				_("Attach a PDF or an image. Other file types cannot be previewed."),
				title=_("Unsupported File"),
			)

	@frappe.whitelist()
	def link_to_document(self, document_name: str | int) -> str:
		# created_document is a Dynamic Link, so a claim always reads back as a string.
		document_name = cstr(document_name)

		claimed, source_file = frappe.db.get_value(
			"Attachment Queue", self.name, ["created_document", "source_file"], for_update=True
		)

		if claimed:
			if claimed == document_name:
				return claimed

			frappe.throw(
				_("{0} has already produced {1} {2}.").format(
					frappe.bold(self.name),
					frappe.bold(_(self.document_type)),
					frappe.bold(claimed),
				)
			)

		if not frappe.db.exists(self.document_type, document_name):
			frappe.throw(
				_("{0} {1} does not exist.").format(
					frappe.bold(_(self.document_type)), frappe.bold(document_name)
				)
			)

		frappe.has_permission(self.document_type, "write", doc=document_name, throw=True)
		self.attach_source_file_to(self.document_type, document_name, source_file)

		# Written last, so the entry only reads as filed once its file is in place.
		self.db_set("created_document", document_name)
		return document_name

	def attach_source_file_to(self, document_type: str, document_name: str, source_file: str) -> None:
		"""Give the target its own File record for the same stored file."""
		file_name = frappe.db.get_value(
			"File",
			{
				"file_url": source_file,
				"attached_to_doctype": self.doctype,
				"attached_to_name": self.name,
			},
		)
		if not file_name:
			frappe.throw(_("The file for {0} is no longer available.").format(frappe.bold(self.name)))

		frappe.get_doc("File", file_name).create_attachment_copy(
			attached_to_doctype=document_type,
			attached_to_name=document_name,
		)

	@staticmethod
	def clear_old_logs(days: int = 30) -> None:
		cutoff = add_to_date(now(), days=-cint(days), as_datetime=True)
		rows = frappe.get_all(
			"Attachment Queue",
			filters={"modified": ("<", cutoff)},
			pluck="name",
		)

		for name in rows:
			frappe.delete_doc("Attachment Queue", name, delete_permanently=True)


def get_file_extension(file_url: str) -> str:
	return Path(file_url.split("?", 1)[0]).suffix.lower()


def has_permission(doc, ptype="read", user=None):
	"""Check for access to the target DocType, not the queue row itself. The queue row is always readable."""
	if not doc.document_type or not frappe.db.exists("DocType", doc.document_type):
		return False

	return frappe.has_permission(doc.document_type, ptype=ptype, user=user)


def get_permission_query_conditions(user: str | None = None):
	"""Keep list queries to the rows whose target DocType the user can read."""
	user = user or frappe.session.user
	if user == "Administrator":
		return None

	readable_doctypes = get_doctypes_with_read(user)
	if not readable_doctypes:
		return "1 = 0"

	return frappe.qb.DocType("Attachment Queue").document_type.isin(readable_doctypes)
