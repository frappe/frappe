# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class QueueDocumentAction(Document):
	def validate(self):
		self.name = self.document_type

	def after_insert(self):
		if not frappe.db.exists(
			"Custom Field", {"dt": self.document_type, "label": "enqueue_action", "fieldtype": "Check"}
		):
			return frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": self.document_type,
					"label": "is_queued",
					"fieldtype": "Check",
					"default": 1,
					"allow_on_submit": 1,
				}
			).insert()

	def on_trash(self):
		frappe.delete_doc(
			"Custom Field", "{0}-{1}".format(self.document_type, "is_queued"), delete_permanently=True
		)
