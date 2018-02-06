## Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
from frappe.exceptions import *
from frappe.model.document import Document
from frappe.utils import  nowdate, parse_val
from frappe.modules.utils import export_module_json, get_doc_module
from six import string_types
from frappe.utils.safe_eval import test_python_expr


class CustomServerAction(Document):
	def validate(self):
		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event == "Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		if self.action_type in ("Create Record", "Update Record") and not (
			self.target_document_type and self.value_mapping):
			frappe.throw(_("Please specify which target document type and fied mapping"))

		if (self.action_type == "Update Record" and self.document_type != self.target_document_type and
			   not self.link_field):
			frappe.throw(_("Please specify link field"))

		if self.action_type in ("Execute Python Code") and not self.code:
			frappe.throw(_("Please specify the python code to be executed"))

		self.validate_forbidden_types()
		self.validate_python_code(self.document_type, 'Condition', self.condition)
		self.validate_python_code(self.document_type, 'Code', self.code)
		self.validate_items()

	def on_update(self):
		frappe.cache().hdel('custom_server_actions', self.document_type)

	def on_trash(self):
		frappe.cache().hdel('custom_server_actions', self.document_type)

	def validate_python_code(self, doctype, field_name, field_to_validate):	
		if field_to_validate:	
			mode='exec' if field_name == 'Code' else 'eval'	
			msg = test_python_expr(field_to_validate, mode=mode)
			frappe.log_error(field_to_validate, mode)
			if msg:
				frappe.throw(_("The {0} '{1}' is invalid, with error {2}").format(field_name, field_to_validate, msg))

	def validate_items(self):
		for item in self.value_mapping:
			if item.type == 'Formula':
				self.validate_python_code(self.target_document_type,'Value', item.value)

	def validate_forbidden_types(self):
		forbidden_document_types = ("Email Queue",)
		if (self.document_type in forbidden_document_types
		    or frappe.get_meta(self.document_type).istable):
			# currently Custom Server Actions don't work on child tables as events are not fired for each record of child table

			frappe.throw(_("Cannot set Custom Server Action on Document Type {0}").format(self.document_type))

	def get_documents_for_today(self):
		'''get list of documents that will be triggered today'''
		docs = []

		diff_days = self.days_in_advance
		if self.event == "Days After":
			diff_days = -diff_days

		for name in frappe.db.sql_list("""select name from `tab{0}` where
			DATE(`{1}`) = ADDDATE(DATE(%s), INTERVAL %s DAY)""".format(self.document_type,
		                                                               self.date_changed), (nowdate(), diff_days or 0)):

			doc = frappe.get_doc(self.document_type, name)

			if self.condition and not frappe.safe_eval(self.condition, None, get_context(doc)):
				continue

			docs.append(doc)

		return docs


@frappe.whitelist()
def get_documents_for_today(custom_server_action):
	custom_server_action = frappe.get_doc('Custom Server Action', custom_server_action)
	custom_server_action.check_permission('read')
	return [d.name for d in custom_server_action.get_documents_for_today()]


def trigger_daily_server_actions():
	trigger_custom_server_actions(None, "daily")


def trigger_custom_server_actions(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send Custom Server Actions while syncing or patching
		return

	if method == "daily":
		for server_action in frappe.db.sql_list("""select name from `tabCustom Server Action`
			where event in ('Days Before', 'Days After') and enabled=1"""):
			server_action = frappe.get_doc("Custom Server Action", server_action)
			for doc in server_action.get_documents_for_today():
				evaluate_server_action(doc, server_action, server_action.event)
				frappe.db.commit()
