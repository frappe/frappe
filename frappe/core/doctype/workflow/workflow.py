# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

from frappe.model.document import Document

class Workflow(Document):

	def validate(self):
		self.set_active()
		self.create_custom_field_for_workflow_state()
		self.update_default_workflow_status()

	def on_update(self):
		frappe.clear_cache(doctype=self.document_type)

	def create_custom_field_for_workflow_state(self):
		frappe.clear_cache(doctype=self.document_type)
		meta = frappe.get_meta(self.document_type)
		if not meta.get_field(self.workflow_state_field):
			# create custom field
			frappe.get_doc({
				"doctype":"Custom Field",
				"dt": self.document_type,
				"__islocal": 1,
				"fieldname": self.workflow_state_field,
				"label": self.workflow_state_field.replace("_", " ").title(),
				"hidden": 1,
				"fieldtype": "Link",
				"options": "Workflow State",
			}).save()

			frappe.msgprint(_("Created Custom Field {0} in {1}").format(self.workflow_state_field,
				self.document_type))

	def update_default_workflow_status(self):
		docstatus_map = {}
		states = self.get("workflow_document_states")
		for d in states:
			if not d.doc_status in docstatus_map:
				frappe.db.sql("""update `tab%s` set `%s` = %s where \
					ifnull(`%s`, '')='' and docstatus=%s""" % (self.document_type, self.workflow_state_field,
						'%s', self.workflow_state_field, "%s"), (d.state, d.doc_status))
				docstatus_map[d.doc_status] = d.state

	def set_active(self):
		if int(self.is_active or 0):
			# clear all other
			frappe.db.sql("""update tabWorkflow set is_active=0
				where document_type=%s""",
				self.document_type)
