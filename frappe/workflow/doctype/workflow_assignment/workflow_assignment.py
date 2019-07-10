# -*- coding: utf-8 -*-
# Copyright (c) 2019, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.model.document import Document

class WorkflowAssignment(Document):
	def validate(self):
		self.create_custom_field_for_workflow()

	def create_custom_field_for_workflow(self):
		def create_custom_field(field, options):
			if not meta.get_field(field):
				# create custom field
				frappe.get_doc({
					"doctype":"Custom Field",
					"dt": self.document_type,
					"__islocal": 1,
					"fieldname": field,
					"label": field.replace("_", " ").title(),
					"hidden": 1,
					"allow_on_submit": 1,
					"no_copy": 1,
					"fieldtype": "Link",
					"options": options,
					"owner": "Administrator"
				}).save()
			created_fields.append(field)

		frappe.clear_cache(doctype=self.document_type)
		meta = frappe.get_meta(self.document_type)
		workflow_state_field = frappe.get_doc('Workflow', self.workflow).workflow_state_field
		created_fields =[]
		create_custom_field(workflow_state_field, 'Workflow State')
		create_custom_field('workflow_def', 'Workflow')
		if created_fields:
			frappe.msgprint(_("Created Custom Fields {0} in {1}").format(','.join(created_fields),
				self.document_type))
