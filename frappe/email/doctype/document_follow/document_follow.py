# Copyright (c) 2019, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return None

	return f"""`tabDocument Follow`.`user` = {frappe.db.escape(user)}"""


def has_permission(doc, ptype="read", user=None):
	user = user or frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return True

	return doc.user == user


class DocumentFollow(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		ref_docname: DF.DynamicLink
		ref_doctype: DF.Link
		user: DF.Link
	# end: auto-generated types

	pass
