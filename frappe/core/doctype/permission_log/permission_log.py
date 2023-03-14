# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
	@property
	def changed_by(self):
		return self.owner

	@property
	def changed_at(self):
		return self.creation


def make_perm_log(
	medium,
	reference_doctype,
	for_role,
	reference_document=None,
	ptype=None,
	value=None,
	action="update",
):
	"""
	actions can be: update, remove, create
	"""

	frappe.get_doc(
		{
			"doctype": "Role Permission Log",
			"medium": medium,
			"ptype": ptype,
			"for_doctype": reference_doctype,
			"for_document": reference_document,
			"for_role": for_role,
			"value": value,
			"action": action,
		}
	).db_insert()
