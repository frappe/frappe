# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe import _

from frappe.model.document import Document
from frappe.model import no_value_fields

class Workflow(Document):
	def validate(self):
		self.set_active()
		self.create_custom_field_for_workflow_state()
		self.update_default_workflow_status()
		self.validate_docstatus()

	def on_update(self):
		self.update_doc_status()
		frappe.clear_cache(doctype=self.document_type)
		frappe.cache().delete_key('workflow_' + self.name) # clear cache created in model/workflow.py

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
				"allow_on_submit": 1,
				"no_copy": 1,
				"fieldtype": "Link",
				"options": "Workflow State",
				"owner": "Administrator"
			}).save()

			frappe.msgprint(_("Created Custom Field {0} in {1}").format(self.workflow_state_field,
				self.document_type))

	def update_default_workflow_status(self):
		docstatus_map = {}
		states = self.get("states")
		for d in states:
			if not d.doc_status in docstatus_map:
				frappe.db.sql("""
					UPDATE `tab{doctype}`
					SET `{field}` = %s
					WHERE ifnull(`{field}`, '') = ''
					AND `docstatus` = %s
				""".format(doctype=self.document_type, field=self.workflow_state_field),
				(d.state, d.doc_status))

				docstatus_map[d.doc_status] = d.state

	def update_doc_status(self):
		'''
			Checks if the docstatus of a state was updated.
			If yes then the docstatus of the document with same state will be updated
		'''
		doc_before_save = self.get_doc_before_save()
		before_save_states, new_states = {}, {}
		if doc_before_save:
			for d in doc_before_save.states:
				before_save_states[d.state] = d
			for d in self.states:
				new_states[d.state] = d

			for key in new_states:
				if key in before_save_states:
					if not new_states[key].doc_status == before_save_states[key].doc_status:
						frappe.db.set_value(self.document_type, {
								self.workflow_state_field: before_save_states[key].state
							},
							'docstatus',
							new_states[key].doc_status,
							update_modified = False)

	def validate_docstatus(self):
		def get_state(state):
			for s in self.states:
				if s.state==state:
					return s

			frappe.throw(frappe._("{0} not a valid State").format(state))

		for t in self.transitions:
			state = get_state(t.state)
			next_state = get_state(t.next_state)

			if state.doc_status=="2":
				frappe.throw(frappe._("Cannot change state of Cancelled Document. Transition row {0}").format(t.idx))

			if state.doc_status=="1" and next_state.doc_status=="0":
				frappe.throw(frappe._("Submitted Document cannot be converted back to draft. Transition row {0}").format(t.idx))

			if state.doc_status=="0" and next_state.doc_status=="2":
				frappe.throw(frappe._("Cannot cancel before submitting. See Transition {0}").format(t.idx))

	def set_active(self):
		if int(self.is_active or 0):
			# clear all other
			frappe.db.sql("""UPDATE `tabWorkflow` SET `is_active`=0
				WHERE `document_type`=%s""",
				self.document_type)

@frappe.whitelist()
def get_fieldnames_for(doctype):
	return [f.fieldname for f in frappe.get_meta(doctype).fields \
		if f.fieldname not in no_value_fields]

@frappe.whitelist()
def get_workflow_state_count(doctype, workflow_state_field, states):
	states = frappe.parse_json(states)
	result = frappe.get_all(
		doctype,
		fields=[workflow_state_field, 'count(*) as count', 'docstatus'],
		filters = {'workflow_state': ['not in', states]},
		group_by = workflow_state_field
	)
	return [r for r in result if r[workflow_state_field]]

