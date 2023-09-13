# Copyright (c) 2023, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class ProposedDocument(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		document_json: DF.Code | None
		document_name: DF.Data | None
		document_type: DF.Link | None
		is_new_doc: DF.Check
	# end: auto-generated types
	pass


def get_permission_query_conditions(user):
	if not user:
		user = frappe.session.user

	if user == "Administrator":
		return ""

	return f"`tabProposed Document`.owner = {frappe.db.escape(user)}"
