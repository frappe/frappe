# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import json

from frappe.model.document import Document
from frappe.utils import get_fullname

class ToDo(Document):
	def validate(self):
		if self.is_new():
			self.add_assign_comment(frappe._("Assigned to {0}").format(get_fullname(self.owner)), "Assigned")
		else:
			cur_status = frappe.db.get_value("ToDo", self.name, "status")
			if cur_status != self.status:
				self.add_assign_comment(frappe._("Assignment closed by {0}".format(get_fullname(frappe.session.user))),
					"Assignment Completed")

	def on_update(self):
		self.update_in_reference()

	def on_trash(self):
		self.update_in_reference()

	def add_assign_comment(self, text, comment_type):
		if not self.reference_type and self.reference_name:
			return

		frappe.get_doc({
			"doctype":"Comment",
			"comment_by": frappe.session.user,
			"comment_type": comment_type,
			"comment_doctype": self.reference_type,
			"comment_docname": self.reference_name,
			"comment": """{text}""".format(text=text)
		}).insert(ignore_permissions=True)

	def update_in_reference(self):
		if not (self.reference_type and self.reference_name):
			return

		try:
			assignments = [d[0] for d in frappe.get_all("ToDo",
				filters={
					"reference_type": self.reference_type,
					"reference_name": self.reference_name,
					"status": "Open"
				},
				fields=["owner"], as_list=True)]

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
def on_doctype_update():
	frappe.db.add_index("ToDo", ["reference_type", "reference_name"])

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
