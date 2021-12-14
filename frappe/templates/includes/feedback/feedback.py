# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from __future__ import unicode_literals

import frappe

from frappe import _
from frappe.utils import add_days, today, get_request_site_address
from frappe.rate_limiter import rate_limit
from frappe.website.doctype.blog_settings.blog_settings import get_feedback_limit

@frappe.whitelist(allow_guest=True)
@rate_limit(key='reference_name', limit=get_feedback_limit, seconds=60*60)
def give_feedback(reference_doctype, reference_name, like):
	like = frappe.parse_json(like)
	ref_doc = frappe.get_doc(reference_doctype, reference_name)
	if ref_doc.disable_feedback == 1:
		return

	filters = {
		"owner": frappe.session.user,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name
	}
	d = frappe.get_all('Feedback', filters=filters, limit=1)
	if d:
		doc = frappe.get_doc('Feedback', d[0].name)
	else:
		doc = doc = frappe.new_doc('Feedback')
		doc.reference_doctype = reference_doctype
		doc.reference_name = reference_name
		doc.ip_address = frappe.local.request_ip
	doc.like = like
	doc.save(ignore_permissions=True)

	return doc

@frappe.whitelist(allow_guest=True)
def get_feedback_data(reference_doctype, reference_name):
	like_count = 0
	if frappe.db.count('Feedback'):
		like_count = frappe.db.count('Feedback', 
			filters = dict(
				reference_doctype = reference_doctype, 
				reference_name = reference_name, 
				like = True
			)
		)

	feedback = frappe.get_all('Feedback',
		fields=['like'],
		filters=dict(
			reference_doctype = reference_doctype,
			reference_name = reference_name,
			ip_address = frappe.local.request_ip,
			owner = frappe.session.user
		)
	)

	user_feedback = feedback[0].like if feedback else ''

	return {"like_count": like_count, "like": user_feedback}

def get_yesterdays_feedback():
	yesterday = add_days(today(), -1)

	feedbacks = frappe.get_all("Feedback",
		fields = ["reference_doctype", "reference_name"],
		filters = {
			"modified": ("between", [yesterday, yesterday]),
			"like": 1
		}
	)
	return feedbacks

@frappe.whitelist(allow_guest=True)
def send_daily_feedback_summary():
	feedbacks = get_yesterdays_feedback()

	if not feedbacks:
		return

	recipients = {}
	for feedback in feedbacks:
		blog = frappe.get_doc(feedback.reference_doctype, feedback.reference_name)

		if blog.owner not in recipients:
			recipients[blog.owner] = {blog.name: 1}
		elif (blog.name not in recipients[blog.owner]):
			recipients[blog.owner].update({blog.name: 1})
		else:
			recipients[blog.owner][blog.name] += 1

	for recipient, blogs in recipients.items():
		recipient = frappe.db.get_value('User', recipient, 'email') or recipient
		is_email_notification_enabled = frappe.db.get_value('Notification Settings', recipient, 'enable_feedback_notification')
		
		if is_email_notification_enabled:
			send_feedback_summary_mail(recipient, blogs)

def send_feedback_summary_mail(recipient, blogs):
	message = ""

	for blog, value in blogs.items():
		blog = frappe.get_doc('Blog Post', blog)

		blog_with_url = "<a href='{0}/{1}'>{2}</a>".format(get_request_site_address(), blog.route, blog.title)

		if value == 1:
			message += "<p>You have received a like on your blog post <b>{0}</b>.</p>".format(blog_with_url)
		else:
			message += "<p><b>{0}</b> people liked your blog post <b>{1}</b>.</p>".format(value, blog_with_url)

	frappe.sendmail(
		recipients=recipient,
		subject=_('Blog Feedback Summary'),
		message= message
	)
