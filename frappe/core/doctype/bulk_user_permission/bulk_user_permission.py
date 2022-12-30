# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class BulkUserPermission(Document):
	def on_submit(self):
		for emp_permission in self.user_permissions:
			if emp_permission and not frappe.get_all("User Permission",{
			'user': self.user, 
			'allow': emp_permission.allow,
			"for_value": emp_permission.for_value, 
			"apply_to_all_doctypes": emp_permission.apply_to_all_document_types,
			"applicable_for":emp_permission.applicable_for,
			"hide_descendants":emp_permission.hide_descendants
			}):
				doc=frappe.get_doc({
				'doctype':'User Permission',
				'user': self.user, 
				'allow': emp_permission.allow,
				"for_value": emp_permission.for_value, 
				"apply_to_all_doctypes": emp_permission.apply_to_all_document_types,
				"applicable_for":emp_permission.applicable_for,
				"hide_descendants":emp_permission.hide_descendants
				})
				doc.save()
