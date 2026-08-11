# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document
from frappe.permissions import get_doctypes_with_read


class TagLink(Document):
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
	pass


def on_doctype_update():
	frappe.db.add_index("Tag Link", ["document_type", "document_name"])
<<<<<<< HEAD
=======


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
>>>>>>> 3beb5a1016 (fix: limit Tag Link queries to doctypes the user can read (#41365))
