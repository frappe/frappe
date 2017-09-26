# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json, os
from frappe import _
from frappe.model.document import Document
from frappe.core.doctype.role.role import get_emails_from_role
from frappe.utils import validate_email_add, nowdate, parse_val, is_html
from frappe.utils.jinja import validate_template
from frappe.modules.utils import export_module_json, get_doc_module
from markdown2 import markdown
from six import string_types

class EmailAlert(Document):
	def onload(self):
		'''load message'''
		if self.is_standard:
			self.message = self.get_template()

	def autoname(self):
		if not self.name:
			self.name = self.subject

	def validate(self):
		validate_template(self.subject)
		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event=="Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_forbidden_types()
		self.validate_condition()
		self.validate_standard()

	def on_update(self):
		frappe.cache().hdel('email_alerts', self.document_type)
		path = export_module_json(self, self.is_standard, self.module)
		if path:
			# js
			if not os.path.exists(path + '.md') and not os.path.exists(path + '.html'):
				with open(path + '.md', 'w') as f:
					f.write(self.message)

			# py
			if not os.path.exists(path + '.py'):
				with open(path + '.py', 'w') as f:
					f.write("""from __future__ import unicode_literals

import frappe

def get_context(context):
	# do your magic here
	pass
""")

	def validate_standard(self):
		if self.is_standard and not frappe.conf.developer_mode:
			frappe.throw(_('Cannot edit Standard Email Alert. To edit, please disable this and duplicate it'))

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, None, get_context(temp_doc))
			except Exception:
				frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))

	def validate_forbidden_types(self):
		forbidden_document_types = ("Email Queue",)
		if (self.document_type in forbidden_document_types
			or frappe.get_meta(self.document_type).istable):
			# currently email alerts don't work on child tables as events are not fired for each record of child table

			frappe.throw(_("Cannot set Email Alert on Document Type {0}").format(self.document_type))

	def get_documents_for_today(self):
		'''get list of documents that will be triggered today'''
		docs = []

		diff_days = self.days_in_advance
		if self.event=="Days After":
			diff_days = -diff_days

		for name in frappe.db.sql_list("""select name from `tab{0}` where
			DATE(`{1}`) = ADDDATE(DATE(%s), INTERVAL %s DAY)""".format(self.document_type,
				self.date_changed), (nowdate(), diff_days or 0)):

			doc = frappe.get_doc(self.document_type, name)

			if self.condition and not frappe.safe_eval(self.condition, None, get_context(doc)):
				continue

			docs.append(doc)

		return docs

	def send(self, doc):
		'''Build recipients and send email alert'''

		def get_attachment(doc):
			""" check print settings are attach the pdf """
			if not self.attach_print:
				return None

			print_settings = frappe.get_doc("Print Settings", "Print Settings")
			if (doc.docstatus == 0 and not print_settings.allow_print_for_draft) or \
				(doc.docstatus == 2 and not print_settings.allow_print_for_cancelled):

				# ignoring attachment as draft and cancelled documents are not allowed to print
				status = "Draft" if doc.docstatus == 0 else "Cancelled"
				frappe.throw(_("""Not allowed to attach {0} document,
					please enable Allow Print For {0} in Print Settings""".format(status)),
					title=_("Error in Email Alert"))
			else:
				return [frappe.attach_print(doc.doctype, doc.name, None, self.print_format)]

		context = get_context(doc)
		recipients = []

		for recipient in self.recipients:
			if recipient.condition:
				if not frappe.safe_eval(recipient.condition, None, context):
					continue
			if recipient.email_by_document_field:
				if validate_email_add(doc.get(recipient.email_by_document_field)):
					recipient.email_by_document_field = doc.get(recipient.email_by_document_field).replace(",", "\n")
					recipients = recipients + recipient.email_by_document_field.split("\n")

				# else:
				# 	print "invalid email"
			if recipient.cc:
				recipient.cc = recipient.cc.replace(",", "\n")
				recipients = recipients + recipient.cc.split("\n")

			#For sending emails to specified role
			if recipient.email_by_role:
				emails = get_emails_from_role(recipient.email_by_role)

				for email in emails:
					recipients = recipients + email.split("\n")

		if not recipients:
			return

		recipients = list(set(recipients))
		subject = self.subject

		context = {"doc": doc, "alert": self, "comments": None}

		if self.is_standard:
			self.load_standard_properties(context)

		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if "{" in subject:
			subject = frappe.render_template(self.subject, context)

		attachments = get_attachment(doc)

		frappe.sendmail(recipients=recipients, subject=subject,
			message= frappe.render_template(self.message, context),
			reference_doctype = doc.doctype,
			reference_name = doc.name,
			attachments = attachments)

		if self.set_property_after_alert:
			frappe.db.set_value(doc.doctype, doc.name, self.set_property_after_alert,
				self.property_value, update_modified = False)
			doc.set(self.set_property_after_alert, self.property_value)

	def get_template(self):
		module = get_doc_module(self.module, self.doctype, self.name)
		def load_template(extn):
			template = ''
			template_path = os.path.join(os.path.dirname(module.__file__),
				frappe.scrub(self.name) + extn)
			if os.path.exists(template_path):
				with open(template_path, 'r') as f:
					template = f.read()
			return template

		return load_template('.html') or load_template('.md')

	def load_standard_properties(self, context):
		'''load templates and run get_context'''
		module = get_doc_module(self.module, self.doctype, self.name)
		if module:
			if hasattr(module, 'get_context'):
				out = module.get_context(context)
				if out: context.update(out)

		self.message = self.get_template()

		if not is_html(self.message):
			self.message = markdown(self.message)

@frappe.whitelist()
def get_documents_for_today(email_alert):
	email_alert = frappe.get_doc('Email Alert', email_alert)
	email_alert.check_permission('read')
	return [d.name for d in email_alert.get_documents_for_today()]

def trigger_daily_alerts():
	trigger_email_alerts(None, "daily")

def trigger_email_alerts(doc, method=None):
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send email alerts while syncing or patching
		return

	if method == "daily":
		for alert in frappe.db.sql_list("""select name from `tabEmail Alert`
			where event in ('Days Before', 'Days After') and enabled=1"""):
			alert = frappe.get_doc("Email Alert", alert)
			for doc in alert.get_documents_for_today():
				evaluate_alert(doc, alert, alert.event)
				frappe.db.commit()

def evaluate_alert(doc, alert, event):
	from jinja2 import TemplateError
	try:
		if isinstance(alert, string_types):
			alert = frappe.get_doc("Email Alert", alert)

		context = get_context(doc)

		if alert.condition:
			if not frappe.safe_eval(alert.condition, None, context):
				return

		if event=="Value Change" and not doc.is_new():
			try:
				db_value = frappe.db.get_value(doc.doctype, doc.name, alert.value_changed)
			except frappe.DatabaseOperationalError as e:
				if e.args[0]==1054:
					alert.db_set('enabled', 0)
					frappe.log_error('Email Alert {0} has been disabled due to missing field'.format(alert.name))
					return

			db_value = parse_val(db_value)
			if (doc.get(alert.value_changed) == db_value) or \
				(not db_value and not doc.get(alert.value_changed)):

				return # value not changed

		if event != "Value Change" and not doc.is_new():
			# reload the doc for the latest values & comments,
			# except for validate type event.
			doc = frappe.get_doc(doc.doctype, doc.name)

		alert.send(doc)
	except TemplateError:
		frappe.throw(_("Error while evaluating Email Alert {0}. Please fix your template.").format(alert))
	except Exception as e:
		frappe.log_error(message=frappe.get_traceback(), title=e)
		frappe.throw(_("Error in Email Alert"))

def get_context(doc):
	return {"doc": doc, "nowdate": nowdate, "frappe.utils": frappe.utils}
