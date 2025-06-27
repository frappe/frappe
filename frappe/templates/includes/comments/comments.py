# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re

import frappe
from frappe import _, scrub
from frappe.rate_limiter import rate_limit
from frappe.utils.html_utils import clean_html
from frappe.website.utils import clear_cache

URLS_COMMENT_PATTERN = re.compile(
	r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)


@frappe.whitelist(allow_guest=True)
@rate_limit(key="reference_name", limit=5, seconds=60 * 60)
def add_comment(comment, comment_email, comment_by, reference_doctype, reference_name, route):
	if frappe.session.user == "Guest":
		if reference_doctype not in ("Web Page"):
			return

		if frappe.db.exists("User", comment_email):
			frappe.throw(_("Please login to post a comment."))

	if not comment.strip():
		frappe.msgprint(_("The comment cannot be empty"))
		return False

	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		frappe.msgprint(_("Comments cannot have links or email addresses"))
		return False

	doc = frappe.get_doc(reference_doctype, reference_name)
	comment = doc.add_comment(text=clean_html(comment), comment_email=comment_email, comment_by=comment_by)

	comment.db_set("published", 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	# revert with template if all clear (no backlinks)
	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
