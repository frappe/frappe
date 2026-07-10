# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import re

import frappe
from frappe import _, scrub
from frappe.rate_limiter import rate_limit
from frappe.utils.html_utils import clean_html
from frappe.website.doctype.blog_settings.blog_settings import get_comment_limit
from frappe.website.utils import clear_cache

URLS_COMMENT_PATTERN = re.compile(
	r"http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+", re.IGNORECASE
)
EMAIL_PATTERN = re.compile(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", re.IGNORECASE)


@frappe.whitelist(allow_guest=True)
@rate_limit(key="reference_name", limit=get_comment_limit, seconds=60 * 60)
def add_comment(
	comment: str,
	comment_email: str,
	comment_by: str,
	reference_doctype: str,
	reference_name: str,
	route: str,
	web_form: str | None = None,
):
	if frappe.session.user == "Guest":
		if reference_doctype not in ("Blog Post", "Web Page"):
			return

		if reference_doctype == "Blog Post" and not frappe.db.get_single_value(
			"Blog Settings", "allow_guest_to_comment"
		):
			return

		if frappe.db.exists("User", comment_email):
			frappe.throw(_("Please login to post a comment."), exc=frappe.AuthenticationError)
	else:
		# override with the logged-in user's identity to prevent spoofing;
		# guests must supply their own name/email in the request
		comment_email = frappe.session.user
		comment_by = frappe.get_value("User", frappe.session.user, "full_name")

	if not comment.strip():
		frappe.msgprint(_("The comment cannot be empty"))
		return False

	if URLS_COMMENT_PATTERN.search(comment) or EMAIL_PATTERN.search(comment):
		frappe.msgprint(_("Comments cannot have links or email addresses"))
		return False

	comment_email = frappe.session.user
	comment_by = frappe.get_value("User", frappe.session.user, "full_name")

	perm_flag = True
	doc = frappe.get_doc(reference_doctype, reference_name)
	if web_form:
		web_form = frappe.get_lazy_doc("Web Form", web_form)
		perm_flag = web_form.doc_type == reference_doctype and web_form.has_web_form_permission(
			reference_doctype, reference_name
		)
	elif not (frappe.session.user == "Guest" and reference_doctype in ("Blog Post", "Web Page")):
		perm_flag = doc.has_permission()

	if not perm_flag:
		if frappe.session.user == "Guest":
			raise frappe.AuthenticationError
		raise frappe.PermissionError

	comment = doc.add_comment(text=clean_html(comment), comment_email=comment_email, comment_by=comment_by)

	comment.db_set("published", 1)

	# since comments are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	if doc.get("route"):
		url = f"{frappe.utils.get_request_site_address()}/{doc.route}#{comment.name}"
	else:
		url = f"{frappe.utils.get_request_site_address()}/app/{scrub(doc.doctype)}/{doc.name}#comment-{comment.name}"

	content = comment.content + "<p><a href='{}' style='font-size: 80%'>{}</a></p>".format(
		url, _("View Comment")
	)

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

	# revert with template if all clear (no backlinks)
	template = frappe.get_template("templates/includes/comments/comment.html")
	return template.render({"comment": comment.as_dict()})
