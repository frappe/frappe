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
				frappe.throw(_("The condition '{0}' is invalid").format(self.condition))

@frappe.whitelist()
def send_feedback_request(reference_doctype, reference_name, trigger=None, details=None, is_manual=False):
	""" send feedback alert """
	details = json.loads(details) if details else \
		get_feedback_request_details(reference_doctype, reference_name, trigger=trigger)
	
	if is_manual:
		is_feedback_request_already_sent(reference_doctype, reference_name)

	feedback_request, url = get_feedback_request_url(reference_doctype,
		reference_name, details.get("recipients"), trigger)

	feedback_url = "Please click <a href='{url}'>here</a> to submit your feedback.".format(url=url)

	# appending feedback url to message body
	details.update({ "message": "{message}<br>{feedback_url}".format(
		message=details.get("message"),
		feedback_url=feedback_url)
	})

	if details:
		frappe.sendmail(**details)
		frappe.db.set_value("Feedback Request", feedback_request, "is_sent", 1)

def trigger_feedback_request(doc, method):
	""" trigger the feedback alert"""

	feedback_trigger = frappe.db.get_value("Feedback Trigger", { "enabled": 1, "document_type": doc.doctype })
	if feedback_trigger:
		frappe.enqueue('frappe.core.doctype.feedback_trigger.feedback_trigger.send_feedback_request', 
			trigger=feedback_trigger, reference_doctype=doc.doctype, reference_name=doc.name, now=frappe.flags.in_test)

@frappe.whitelist()
def get_feedback_request_details(reference_doctype, reference_name, trigger=None, request=None):
	feedback_url = ""

	if not trigger and not request and not frappe.db.get_value("Feedback Trigger", { "document_type": reference_doctype }):
		frappe.throw("Can not find Feedback Trigger for {0}".format(reference_name))
	elif not trigger and request:
		trigger = frappe.db.get_value("Feedback Request", request, "feedback_trigger")
	else:
		trigger = frappe.db.get_value("Feedback Trigger", { "document_type": reference_doctype })

	if not trigger:
		frappe.throw(_("Feedback Trigger not found"))

	# check if feedback request mail is already sent but feedback is not submitted
	# to avoid sending multiple feedback request mail
	is_feedback_request_already_sent(reference_doctype, reference_name)

	feedback_trigger = frappe.get_doc("Feedback Trigger", trigger)
	doc = frappe.get_doc(reference_doctype, reference_name)

	context = get_context(doc)

	recipients = doc.get(feedback_trigger.email_fieldname, None)
	communications = frappe.get_all("Communication", filters={
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
		"communication_type": "Communication"
	}, fields=["name"])

	if recipients and eval(feedback_trigger.condition, context) and len(communications) >= 1:
		subject = feedback_trigger.subject
		context.update({ "feedback_trigger": feedback_trigger })

		if "{" in subject:
			subject = frappe.render_template(feedback_trigger.subject, context)

		feedback_request_message = frappe.render_template(feedback_trigger.message, context)

		return {
			"subject": subject,
			"recipients": recipients,
			"reference_name":doc.name,
			"reference_doctype":doc.doctype,
			"message": feedback_request_message,
		}
	else:
		frappe.throw("Feedback conditions does not match !!")

def get_feedback_request_url(reference_doctype, reference_name, recipients, trigger="Manual"):
	feedback_request = frappe.get_doc({
		"doctype": "Feedback Request",
		"reference_name": reference_name,
		"reference_doctype": reference_doctype,
		"feedback_trigger": trigger
	}).insert(ignore_permissions=True)

	feedback_url = "{base_url}/feedback?reference_doctype={doctype}&reference_name={docname}&email={email_id}&key={nonce}".format(	
		base_url=get_url(),
		doctype=reference_doctype,
		docname=reference_name,
		email_id=recipients,
		nonce=feedback_request.name
	)

	return [ feedback_request.name, feedback_url ]

def is_feedback_request_already_sent(reference_doctype, reference_name):
	feedback_request = frappe.get_all("Feedback Request", {
		"is_sent": 1,
		"is_feedback_submitted": 0,
		"reference_name": reference_name,
		"reference_doctype": reference_doctype
	}, ["name"])

	if feedback_request:
		frappe.throw(_("Feedback request mail has been already sent to the recipient"))

def get_enabled_feedback_trigger():
	""" get mapper of all the enable feedback trigger """

	triggers = frappe.get_all("Feedback Trigger", filters={"enabled": 1},
		fields=["document_type", "name"], as_list=True)

	triggers = { dt[0]: dt[1] for dt in triggers }
	return triggers

def get_context(doc):
	return { "doc": doc }
