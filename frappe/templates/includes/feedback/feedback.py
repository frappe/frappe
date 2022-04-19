# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.website.doctype.blog_settings.blog_settings import get_feedback_limit


@frappe.whitelist(allow_guest=True)
@rate_limit(key="reference_name", limit=get_feedback_limit, seconds=60 * 60)
def add_feedback(reference_doctype, reference_name, rating, feedback):
	doc = frappe.get_doc(reference_doctype, reference_name)
	if doc.disable_feedback == 1:
		return

	doc = frappe.new_doc("Feedback")
	doc.reference_doctype = reference_doctype
	doc.reference_name = reference_name
	doc.rating = rating
	doc.feedback = feedback
	doc.ip_address = frappe.local.request_ip
	doc.save(ignore_permissions=True)

	subject = _("New Feedback on {0}: {1}").format(reference_doctype, reference_name)
	send_mail(doc, subject)
	return doc


@frappe.whitelist()
def update_feedback(reference_doctype, reference_name, rating, feedback):
	doc = frappe.get_doc(reference_doctype, reference_name)
	if doc.disable_feedback == 1:
		return

	filters = {
		"owner": frappe.session.user,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
	}
	d = frappe.get_all("Feedback", filters=filters, limit=1)
	doc = frappe.get_doc("Feedback", d[0].name)
	doc.rating = rating
	doc.feedback = feedback
	doc.save(ignore_permissions=True)

	subject = _("Feedback updated on {0}: {1}").format(reference_doctype, reference_name)
	send_mail(doc, subject)
	return doc


def send_mail(feedback, subject):
	doc = frappe.get_doc(feedback.reference_doctype, feedback.reference_name)

	message = "<p>{0} ({1})</p>".format(
		feedback.feedback, feedback.rating
	) + "<p><a href='{0}/app/feedback/{1}' style='font-size: 80%'>{2}</a></p>".format(
		frappe.utils.get_request_site_address(), feedback.name, _("View Feedback")
	)

	# notify creator
	frappe.sendmail(
		recipients=frappe.db.get_value("User", doc.owner, "email") or doc.owner,
		subject=subject,
		message=message,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)
