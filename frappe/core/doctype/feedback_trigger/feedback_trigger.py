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
		feedback_request = details.pop("feedback_request")
		frappe.sendmail(**details)
		frappe.db.set_value("Feedback Request", feedback_request, "is_sent", 1)

def trigger_feedback_alert(doc, method):
	""" trigger the feedback alert"""

	feedback_trigger = frappe.db.get_value("Feedback Trigger", { "enabled": 1, "document_type": doc.doctype })
	if feedback_trigger:
		frappe.enqueue('frappe.core.doctype.feedback_trigger.feedback_trigger.send_feedback_alert', 
			trigger=feedback_trigger, reference_doctype=doc.doctype, reference_name=doc.name, now=frappe.flags.in_test)

@frappe.whitelist()
def get_feedback_alert_details(reference_doctype, reference_name, trigger=None, request=None):
	feedback_url = ""

	if not trigger and not request:
		frappe.throw("Can not find Feedback Alert for {0}".format(reference_name))
	elif not trigger and request:
		trigger = frappe.db.get_value("Feedback Request", request, "feedback_trigger")

	# check if feedback mail alert is already sent but feedback is not submitted
	# to avoid sending multiple feedback mail alerts

	feedback_requests = frappe.get_all("Feedback Request", {
		"is_sent": 1,
		"is_feedback_submitted": 0,
		"reference_name": reference_name,
		"reference_doctype": reference_doctype
	}, ["name"])
	if feedback_requests:
		frappe.throw(_("Feedback Alert Mail has been already sent to the recipient"))

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
		context.update({ "alert": feedback_trigger, "feedback_url": feedback_url })

		if "{" in subject:
			subject = frappe.render_template(feedback_trigger.subject, context)

		feedback_alert_message = frappe.render_template(feedback_trigger.message, context)

		return {
			"subject": subject,
			"recipients": recipients,
			"reference_name":doc.name,
			"reference_doctype":doc.doctype,
			"message": feedback_alert_message,
			"feedback_request": feedback_request.name
		}
	else:
		return None
	

def get_context(doc):
	return { "doc": doc }
