# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class PermissionLog(Document):
	@property
	def changed_by(self):
		return self.owner


def make_perm_log():
	frappe.get_doc(
		{
			"doctype": "Permission Log",
		}
	).db_insert()
