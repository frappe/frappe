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
		frappe.cache().delete_value('feedback_triggers')
		validate_template(self.subject)
		validate_template(self.message)
		self.validate_condition()

	def on_trash(self):
		frappe.cache().delete_value('feedback_triggers')

	def validate_condition(self):
		temp_doc = frappe.new_doc(self.document_type)
		if self.condition:
			try:
				frappe.safe_eval(self.condition, None, get_context(temp_doc))
			except:
				frappe.throw(_("The condition '{0}' is invalid").format(self.condition))

def trigger_feedback_request(doc, method):
	"""Trigger the feedback alert, or delete feedback requests on delete"""

	def _get():
		triggers = {}
		if not (frappe.flags.in_migrate or frappe.flags.in_install):
			for d in frappe.get_all('Feedback Trigger', dict(enabled=1), ['name', 'document_type']):
				triggers[d.document_type] = d.name

		return triggers

	feedback_triggers = frappe.cache().get_value('feedback_triggers', _get)
	if doc.doctype in feedback_triggers:
		if doc.flags.in_delete:
			frappe.enqueue('frappe.core.doctype.feedback_trigger.feedback_trigger.delete_feedback_request_and_feedback',
				reference_doctype=doc.doctype, reference_name=doc.name, now=frappe.flags.in_test)
		else:
			frappe.enqueue('frappe.core.doctype.feedback_trigger.feedback_trigger.send_feedback_request',
				trigger=feedback_triggers[doc.doctype], reference_doctype=doc.doctype,
				reference_name=doc.name, now=frappe.flags.in_test)

@frappe.whitelist()
def send_feedback_request(reference_doctype, reference_name, trigger="Manual", details=None, is_manual=False):
	""" send feedback alert """

	if is_feedback_request_already_sent(reference_doctype, reference_name, is_manual=is_manual):
		frappe.msgprint(_("Feedback Request is already sent to user"))
		return None

	details = json.loads(details) if details else \
		get_feedback_request_details(reference_doctype, reference_name, trigger=trigger)

	if not details:
		return None

	feedback_request, url = get_feedback_request_url(reference_doctype,
		reference_name, details.get("recipients"), trigger)

	feedback_msg = frappe.render_template("templates/emails/feedback_request_url.html", { "url": url })

	# appending feedback url to message body
	message = "{message}{feedback_msg}".format(
		message=details.get("message"),
		feedback_msg=feedback_msg
	)
	details.update({
		"message": message,
		"header": [details.get('subject'), 'blue']
	})

	if details:
		frappe.sendmail(**details)
		frappe.db.set_value("Feedback Request", feedback_request, "is_sent", 1)


@frappe.whitelist()
def get_feedback_request_details(reference_doctype, reference_name, trigger="Manual", request=None):
	if not frappe.db.get_value(reference_doctype, reference_name):
		# reference document is either deleted or renamed
		return
	elif not trigger and not request and not frappe.db.get_value("Feedback Trigger", { "document_type": reference_doctype }):
		return
	elif not trigger and request:
		trigger = frappe.db.get_value("Feedback Request", request, "feedback_trigger")
	else:
		trigger = frappe.db.get_value("Feedback Trigger", { "document_type": reference_doctype })

	if not trigger:
		return

	feedback_trigger = frappe.get_doc("Feedback Trigger", trigger)

	doc = frappe.get_doc(reference_doctype, reference_name)
	context = get_context(doc)

	recipients = doc.get(feedback_trigger.email_fieldname, None)
	if feedback_trigger.check_communication:
		communications = frappe.get_all("Communication", filters={
			"reference_doctype": reference_doctype,
			"reference_name": reference_name,
			"communication_type": "Communication",
			"sent_or_received": "Sent"
		}, fields=["name"])

		if len(communications) < 1:
			frappe.msgprint(_("At least one reply is mandatory before requesting feedback"))
			return None

	if recipients and frappe.safe_eval(feedback_trigger.condition, None, context):
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
		frappe.msgprint(_("Feedback conditions do not match"))
		return None

def get_feedback_request_url(reference_doctype, reference_name, recipients, trigger="Manual"):
	""" prepare the feedback request url """
	is_manual = 1 if trigger == "Manual" else 0
	feedback_request = frappe.get_doc({
		"is_manual": is_manual,
		"feedback_trigger": trigger,
		"doctype": "Feedback Request",
		"reference_name": reference_name,
		"reference_doctype": reference_doctype,
	}).insert(ignore_permissions=True)

	feedback_url = "{base_url}/feedback?reference_doctype={doctype}&reference_name={docname}&email={email_id}&key={nonce}".format(
		base_url=get_url(),
		doctype=reference_doctype,
		docname=reference_name,
		email_id=recipients,
		nonce=feedback_request.key
	)

	return [ feedback_request.name, feedback_url ]

def is_feedback_request_already_sent(reference_doctype, reference_name, is_manual=False):
	"""
		check if feedback request mail is already sent but feedback is not submitted
		to avoid sending multiple feedback request mail
	"""
	is_request_sent = False
	filters = {
		"is_sent": 1,
		"reference_name": reference_name,
		"is_manual": 1 if is_manual else 0,
		"reference_doctype": reference_doctype
	}

	if is_manual:
		filters.update({ "is_feedback_submitted": 0 })

	feedback_request = frappe.get_all("Feedback Request", filters=filters, fields=["name"])

	if feedback_request: is_request_sent = True
	return is_request_sent

def get_enabled_feedback_trigger():
	""" get mapper of all the enable feedback trigger """

	triggers = frappe.get_all("Feedback Trigger", filters={"enabled": 1},
		fields=["document_type", "name"], as_list=True)

	triggers = { dt[0]: dt[1] for dt in triggers }
	return triggers

def get_context(doc):
	return { "doc": doc }

def delete_feedback_request_and_feedback(reference_doctype, reference_name):
	""" delete all the feedback request and feedback communication """
	if not all([reference_doctype, reference_name]):
		return

	feedback_requests = frappe.get_all("Feedback Request", filters={
		"is_feedback_submitted": 0,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name
	})

	communications = frappe.get_all("Communication", {
		"communication_type": "Feedback",
		"reference_doctype": reference_doctype,
		"reference_name": reference_name
	})

	for request in feedback_requests:
		frappe.delete_doc("Feedback Request", request.get("name"), ignore_permissions=True)

	for communication in communications:
		frappe.delete_doc("Communication", communication.get("name"), ignore_permissions=True)
