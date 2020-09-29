# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import re
from frappe.website.render import clear_cache
from frappe.utils import add_to_date, now

from frappe import _

@frappe.whitelist()
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	doc = frappe.get_doc(reference_doctype, reference_name)

	if not comment.strip():
		frappe.msgprint(_('The comment cannot be empty'))
		return False

	url_regex = re.compile(r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE)
	email_regex = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)

	if url_regex.search(comment) or email_regex.search(comment):
		frappe.msgprint(_('Comments cannot have links or email addresses'))
		return False

	if not comment_email == frappe.session.user:
		comment_email = frappe.session.user

	comments_count = frappe.db.count("Comment", {
		"comment_type": "Comment",
		"comment_email": frappe.session.user,
		"creation": (">", add_to_date(now(), hours=-1))
	})

	if comments_count > 20:
		frappe.msgprint(_('Hourly comment limit reached for: {0}').format(frappe.bold(frappe.session.user)))
		return False

	comment = doc.add_comment(
		text=comment,
		comment_email=comment_email,
		comment_by=comment_by)

	comment.db_set('published', 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	content = (comment.content
		+ "<p><a href='{0}/desk#Form/Comment/{1}' style='font-size: 80%'>{2}</a></p>".format(frappe.utils.get_request_site_address(),
			comment.name,
			_("View Comment")))

	# notify creator
	frappe.sendmail(
		recipients=frappe.db.get_value('User', doc.owner, 'email') or doc.owner,
		subject=_('New Comment on {0}: {1}').format(doc.doctype, doc.name),
		message=content,
		reference_doctype=doc.doctype,
		reference_name=doc.name
	)

	# revert with template if all clear (no backlinks)
	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
