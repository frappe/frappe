# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import json
import frappe
from frappe import _
from frappe.utils import get_url
from frappe.model.document import Document
from frappe.utils.jinja import validate_template

class FeedbackTrigger(Document):
	def validate(self):
		validate_template(self.subject)
		validate_template(self.message)
		self.validate_condition()

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				eval(self.condition, get_context(temp_doc))
			except:
				frappe.throw(_("The Condition '{0}' is invalid").format(self.condition))

@frappe.whitelist()
def send_feedback_alert(reference_doctype, reference_name, trigger=None, alert_details=None):
	""" send feedback alert """
	details = json.loads(alert_details) if alert_details else \
		get_feedback_alert_details(reference_doctype, reference_name, trigger=trigger)

	if details:	
		frappe.sendmail(**details)
	else:
		frappe.throw(_("Can not find Feedback Details"))

def trigger_feedback_alert(doc, method):
	""" trigger the feedback alert"""

	name = frappe.db.get_value("Feedback Trigger", { "enabled": 1, "document_type": doc.doctype })
	if name:
		frappe.enqueue('frappe.core.doctype.feedback_trigger.feedback_trigger.send_feedback_alert', 
			trigger=name, reference_doctype=doc.doctype, reference_name=doc.name)

@frappe.whitelist()
def get_feedback_alert_details(reference_doctype, reference_name, trigger=None, request=None):
	feedback_url = ""

	if not trigger and not request:
		frappe.throw("Can not find Feedback Alert for {0}".format(reference_name))
	elif not trigger and request:
		trigger = frappe.db.get_value("Feedback Request", request, "feedback_trigger")

	feedback_trigger = frappe.get_doc("Feedback Trigger", trigger)
	doc = frappe.get_doc(reference_doctype, reference_name)

	context = get_context(doc)

	recipients = doc.get(feedback_trigger.email_fieldname, None)
	if recipients and eval(feedback_trigger.condition, context):
		subject = feedback_trigger.subject
		feedback_request = frappe.get_doc({
			"doctype": "Feedback Request",
			"reference_name": doc.name,
			"reference_doctype": doc.doctype,
			"feedback_trigger": feedback_trigger.name
		}).insert(ignore_permissions=True)

		feedback_url = "{base_url}/feedback?reference_doctype={doctype}&reference_name={docname}&email={email_id}&key={nonce}".format(	
							base_url=get_url(),
							doctype=doc.doctype,
							docname=doc.name,
							email_id=recipients,
							nonce=feedback_request.name
						)
		context = {"doc": doc, "alert": feedback_trigger, "comments": None, "feedback_url": feedback_url}

		if doc.get("_comments"):
			context["comments"] = json.loads(doc.get("_comments"))

		if "{" in subject:
			subject = frappe.render_template(feedback_trigger.subject, context)

		feedback_alert_message = frappe.render_template(feedback_trigger.message, context)

		return {
			"subject": subject,
			"recipients": recipients,
			"reference_name":doc.name,
			"reference_doctype":doc.doctype,
			"message": feedback_alert_message
		}
	else:
		return None
	

def get_context(doc):
	return { "doc": doc }
