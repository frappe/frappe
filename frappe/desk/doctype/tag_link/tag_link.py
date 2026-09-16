# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read


class TagLink(Document):
	_DOCTYPE_NAME = "Tag Link"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		document_name: DF.DynamicLink | None
		document_type: DF.Link | None
		tag: DF.Link | None
		title: DF.Data | None

	# end: auto-generated types

	no_feed_on_delete = True

	def clear_cache(self):
		super().clear_cache()
		if has_tags(self.document_type):
			frappe.client_cache.delete_value(f"doctype_has_tags::{self.document_type}")

	def after_insert(self):
		self.notify_change("add")

	def on_trash(self):
		self.notify_change("delete")

	def notify_change(self, action):
		"""Tell the tagged document's room that its `tags` bucket changed."""
		frappe.publish_realtime(
			"docinfo_update",
			{
				"doc": {
					"reference_doctype": self.document_type,
					"reference_name": self.document_name,
					**self.as_dict(),
				},
				"key": "tags",
				"action": action,
			},
			doctype=self.document_type,
			docname=self.document_name,
			after_commit=True,
		)


def on_doctype_update():
	frappe.db.add_index("Tag Link", ["document_type", "document_name"])


def get_permission_query_conditions(user: str | None = None) -> str:
	user = user or frappe.session.user

	if user == "Administrator":
		return ""

	readable_doctypes = ", ".join(repr(dt) for dt in get_doctypes_with_read(user))
	if not readable_doctypes:
		return " 1 = 0 "

	return f""" `tabTag Link`.`document_type` in ({readable_doctypes}) """


def has_tags(doctype: str):
	"""Short circuit checks for tags by first checking if users even uses tags"""

	def check_db():
		return frappe.db.exists("Tag Link", {"document_type": doctype})

	return frappe.client_cache.get_value(f"doctype_has_tags::{doctype}", generator=check_db)
