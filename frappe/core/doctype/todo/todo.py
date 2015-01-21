# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json

from frappe.model.document import Document

class ToDo(Document):
	def validate(self):
		if self.is_new():
			self.add_comment(frappe._("Assigned to {0}").format(self.owner), "Assigned")
		else:
			cur_status = frappe.db.get_value("ToDo", self.name, "status")
			if cur_status != self.status:
				self.add_comment(frappe._("Assignment Status Changed"), "Assignment Completed")

	def on_update(self):
		self.update_in_reference()

	def on_trash(self):
		self.update_in_reference()

	def add_comment(self, text, comment_type):
		if not self.reference_type and self.reference_name:
			return

		frappe.get_doc({
			"doctype":"Comment",
			"comment_by": frappe.session.user,
			"comment_type": comment_type,
			"comment_doctype": self.reference_type,
			"comment_docname": self.reference_name,
			"comment": """<div>{text}:
				<a href='#Form/ToDo/{name}'>{status}: {description}</a></div>""".format(text=text,
					status = frappe._(self.status),
					name = self.name,
					description = self.description)
		}).insert(ignore_permissions=True)

	def update_in_reference(self):
		if not (self.reference_type and self.reference_name):
			return

		try:
			assignments = [d[0] for d in frappe.get_list("ToDo",
				filters={
					"reference_type": self.reference_type,
					"reference_name": self.reference_name,
					"status": "Open"
				},
				fields=["owner"], ignore_permissions=True, as_list=True)]

			assignments.reverse()
			frappe.db.set_value(self.reference_type, self.reference_name,
				"_assign", json.dumps(assignments))

		except Exception, e:
			if e.args[0] == 1146 and frappe.flags.in_install:
				# no table
				return

			elif e.args[0]==1054:
				from frappe.model.db_schema import add_column
				add_column(self.reference_type, "_assign", "Text")
				self.update_in_reference()

			else:
				raise

# NOTE: todo is viewable if either owner or assigned_to or System Manager in roles

def get_permission_query_conditions(user):
	if not user: user = frappe.session.user

	if "System Manager" in frappe.get_roles(user):
		return None
	else:
		return """(tabToDo.owner = '{user}' or tabToDo.assigned_by = '{user}')"""\
			.format(user=frappe.db.escape(user))

def has_permission(doc, user):
	if "System Manager" in frappe.get_roles(user):
		return True
	else:
		return doc.owner==user or doc.assigned_by==user
