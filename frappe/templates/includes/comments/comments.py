# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import frappe.utils
from frappe.website.render import clear_cache

from frappe import _

@frappe.whitelist(allow_guest=True)
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	doc = frappe.get_doc(reference_doctype, reference_name)

	if len(comment) < 10:
		frappe.msgprint(_('Comment Should be atleast 10 characters'))
		return ''

	blacklist = ['http://', 'https://', '@gmail.com']

	if any([b in comment for b in blacklist]):
		frappe.msgprint(_('Comments cannot have links or email addresses'))
		return ''

	comment = doc.add_comment(
		text = comment,
		comment_email = comment_email,
		comment_by = comment_by)

	comment.db_set('published', 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	content = (comment.content
		+ "<p><a href='{0}/desk/#Form/Comment/{1}' style='font-size: 80%'>{2}</a></p>".format(frappe.utils.get_request_site_address(),
			comment.name,
			_("View Comment")))

	# notify creator
	frappe.sendmail(
		recipients = frappe.db.get_value('User', doc.owner, 'email') or doc.owner,
		subject = _('New Comment on {0}: {1}').format(doc.doctype, doc.name),
		message = content,
		reference_doctype=doc.doctype,
		reference_name=doc.name
	)

	if comment.published:
		# revert with template if all clear (no backlinks)
		template = frappe.get_template("templates/includes/comments/comment.html")

		return template.render({"comment": comment.as_dict()})

	else:
		return ''
