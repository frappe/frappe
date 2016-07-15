# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
import json
from frappe import _
from frappe.model.document import Document
from frappe.utils import validate_email_add, nowdate
from frappe.utils.jinja import validate_template

class EmailAlert(Document):
	def validate(self):
		validate_template(self.subject)
		validate_template(self.message)

		if self.event in ("Days Before", "Days After") and not self.date_changed:
			frappe.throw(_("Please specify which date field must be checked"))

		if self.event=="Value Change" and not self.value_changed:
			frappe.throw(_("Please specify which value field must be checked"))

		self.validate_forbidden_types()
		self.validate_condition()

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				eval(self.condition, get_context(temp_doc))
			except:
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

			if self.condition and not eval(self.condition, get_context(doc)):
				continue

			docs.append(doc)

		return docs

@frappe.whitelist()
def get_documents_for_today(email_alert):
	email_alert = frappe.get_doc('Email Alert', email_alert)
	email_alert.check_permission('read')
	return [d.name for d in email_alert.get_documents_for_today()]

def trigger_daily_alerts():
	trigger_email_alerts(None, "daily")

def trigger_email_alerts(doc, method=None):
	from jinja2 import TemplateError
	if frappe.flags.in_import or frappe.flags.in_patch:
		# don't send email alerts while syncing or patching
		return

	if method == "daily":

		for alert in frappe.db.sql_list("""select name from `tabEmail Alert`
			where event in ('Days Before', 'Days After') and enabled=1"""):
			alert = frappe.get_doc("Email Alert", alert)
			for doc in alert.get_documents_for_today():
				evaluate_alert(doc, alert, alert.event)
	else:
		if method in ("on_update", "validate") and doc.flags.in_insert:
			# don't call email alerts multiple times for inserts
			# on insert only "New" type alert must be called
			return

		eevent = {
			"on_update": "Save",
			"after_insert": "New",
			"validate": "Value Change",
			"on_submit": "Submit",
			"on_cancel": "Cancel",
		}[method]

		for alert in frappe.db.sql_list("""select name from `tabEmail Alert`
			where document_type=%s and event=%s and enabled=1""", (doc.doctype, eevent)):
			try:
				evaluate_alert(doc, alert, eevent)
			except TemplateError:
				frappe.throw(_("Error while evaluating Email Alert {0}. Please fix your template.").format(alert))

def evaluate_alert(doc, alert, event):
	if isinstance(alert, basestring):
		alert = frappe.get_doc("Email Alert", alert)

	context = get_context(doc)

	if alert.condition:
		if not eval(alert.condition, context):
			return

	if event=="Value Change" and not doc.is_new():
		if doc.get(alert.value_changed) == frappe.db.get_value(doc.doctype,
			doc.name, alert.value_changed):
			return # value not changed

	for recipient in alert.recipients:
		recipients = []
		if recipient.condition:
			if not eval(recipient.condition, context):
				continue
		if recipient.email_by_document_field:
			if validate_email_add(doc.get(recipient.email_by_document_field)):
				recipients.append(doc.get(recipient.email_by_document_field))
			# else:
			# 	print "invalid email"
		if recipient.cc:
			recipient.cc = recipient.cc.replace(",", "\n")
			recipients = recipients + recipient.cc.split("\n")

	if not recipients:
		return

	subject = alert.subject

	if event != "Value Change" and not doc.is_new():
		# reload the doc for the latest values & comments,
		# except for validate type event.
		doc = frappe.get_doc(doc.doctype, doc.name)

	context = {"doc": doc, "alert": alert, "comments": None}

	if doc.get("_comments"):
		context["comments"] = json.loads(doc.get("_comments"))

	if "{" in subject:
		subject = frappe.render_template(alert.subject, context)

	frappe.sendmail(recipients=recipients, subject=subject,
		message= frappe.render_template(alert.message, context), reference_doctype = doc.doctype, reference_name = doc.name,
		attachments = [frappe.attach_print(doc.doctype, doc.name)] if alert.attach_print else None)

def get_context(doc):
	return {"doc": doc, "nowdate": nowdate}

