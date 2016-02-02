# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe
import frappe.utils, markdown2
from frappe.website.render import clear_cache

from frappe import _

@frappe.whitelist(allow_guest=True)
def add_comment(args=None):
	"""
		args = {
			'comment': '',
			'comment_by': '',
			'comment_by_fullname': '',
			'comment_doctype': '',
			'comment_docname': '',
			'page_name': '',
		}
	"""

	if not args:
		args = frappe.local.form_dict
	args['doctype'] = "Comment"

	page_name = args.get("page_name")
	if "page_name" in args:
		del args["page_name"]
	if "cmd" in args:
		del args["cmd"]

	comment = frappe.get_doc(args)
	comment.comment_type = "Comment"
	comment.flags.ignore_permissions = True
	comment.insert()

	# since comments are embedded in the page, clear the web cache
	clear_cache(page_name)

	# notify commentors
	commentors = [d[0] for d in frappe.db.sql("""select comment_by from tabComment where
		comment_doctype=%s and comment_docname=%s and
		unsubscribed=0""", (comment.comment_doctype, comment.comment_docname))]

	owner = frappe.db.get_value(comment.comment_doctype, comment.comment_docname, "owner")
	recipients = list(set(commentors if owner=="Administrator" else (commentors + [owner])))

	message = _("{0} by {1}").format(markdown2.markdown(args.get("comment")), comment.comment_by_fullname)
	message += "<p><a href='{0}/{1}' style='font-size: 80%'>{2}</a></p>".format(frappe.utils.get_request_site_address(),
		page_name, _("View it in your browser"))

	from frappe.email.bulk import send

	send(recipients=recipients,
		subject = _("New comment on {0} {1}").format(comment.comment_doctype, comment.comment_docname),
		message = message,
		reference_doctype=comment.comment_doctype, reference_name=comment.comment_docname)

	template = frappe.get_template("templates/includes/comments/comment.html")

	return template.render({"comment": comment.as_dict()})
