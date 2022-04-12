# Copyright (c) 2022, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document

class EnqueueDocumentActionSetting(Document):
	def validate(self):
		old_table = self._doc_before_save.get('enqueue_selected_action')
		current_table = self.get('enqueue_selected_action')

		if len(old_table) != len(current_table):
			if len(old_table) > len(current_table):
				diff = get_difference(old_table, current_table)
				remove_queue_action_field(diff)

			if len(old_table) < len(current_table):
				diff = get_difference(current_table, old_table)
				add_queue_action_field(diff)


def get_difference(old_table, current_table):
	current_doctype_list = []
	old_doctype_list = []
	for d in current_table:
		current_doctype_list.append(d.document_type)
	for d in old_table:
		old_doctype_list.append(d.document_type)

	return list(set(old_doctype_list).difference(set(current_doctype_list)))

def add_queue_action_field(diff):
	for data in diff:
		if not frappe.db.exists("Custom Field", {"dt": data, "label": "enqueue_action", "fieldtype": "Check"}):
			return frappe.get_doc({
				"doctype": "Custom Field",
				"dt": data,
				"label": "enqueue_action",
				"fieldtype": "Check",
				"default": 1,
				"allow_on_submit": 1
			}).insert()

def remove_queue_action_field(diff):
	for d in diff:
		frappe.delete_doc("Custom Field", '{0}-{1}'.format(d, "enqueue_action"), delete_permanently=True)

