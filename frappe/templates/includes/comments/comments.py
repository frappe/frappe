# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import re

import frappe
from frappe import _
from frappe.utils import add_to_date, now
from frappe.website.render import clear_cache


@frappe.whitelist(allow_guest=True)
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	if frappe.session.user == "Guest":
		if reference_doctype not in ("Blog Post", "Web Page"):
			return

		if reference_doctype == "Blog Post" and not frappe.db.get_single_value(
			"Blog Settings", "allow_guest_to_comment"
		):
			return

		if frappe.db.exists("User", comment_email):
			frappe.throw(_("Please login to post a comment."))

	if not comment.strip():
		frappe.msgprint(_("The comment cannot be empty"))
		return False

	url_regex = re.compile(
		r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE
	)
	email_regex = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)

	if url_regex.search(comment) or email_regex.search(comment):
		frappe.msgprint(_("Comments cannot have links or email addresses"))
		return False

<<<<<<< HEAD
	comments_count = frappe.db.count(
		"Comment",
		{
			"comment_type": "Comment",
			"comment_email": comment_email,
			"creation": (">", add_to_date(now(), hours=-1)),
		},
=======
	doc = frappe.get_doc(reference_doctype, reference_name)
	comment = doc.add_comment(
		text=clean_html(comment), comment_email=comment_email, comment_by=comment_by
>>>>>>> e5b1b8d681 (fix: improved validation in `add_comment` (#20520))
	)

	if comments_count > 20:
		frappe.msgprint(_("Hourly comment limit reached for: {0}").format(frappe.bold(comment_email)))
		return False

	comment = doc.add_comment(text=comment, comment_email=comment_email, comment_by=comment_by)

	comment.db_set("published", 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	content = (
		comment.content
		+ "<p><a href='{0}/app/Form/Comment/{1}' style='font-size: 80%'>{2}</a></p>".format(
			frappe.utils.get_request_site_address(), comment.name, _("View Comment")
		)
	)

<<<<<<< HEAD
	# notify creator
	frappe.sendmail(
		recipients=frappe.db.get_value("User", doc.owner, "email") or doc.owner,
		subject=_("New Comment on {0}: {1}").format(doc.doctype, doc.name),
		message=content,
		reference_doctype=doc.doctype,
		reference_name=doc.name,
	)
=======
	if doc.doctype != "Blog Post" or doc.enable_email_notification:
		# notify creator
		creator_email = frappe.db.get_value("User", doc.owner, "email") or doc.owner
		subject = _("New Comment on {0}: {1}").format(doc.doctype, doc.get_title())

		frappe.sendmail(
			recipients=creator_email,
			subject=subject,
			message=content,
			reference_doctype=doc.doctype,
			reference_name=doc.name,
		)
>>>>>>> e5b1b8d681 (fix: improved validation in `add_comment` (#20520))

	# revert with template if all clear (no backlinks)
	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
