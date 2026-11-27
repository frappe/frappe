# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.website.doctype.blog_settings.blog_settings import get_like_limit
from frappe.website.utils import clear_cache


@frappe.whitelist(allow_guest=True)
@rate_limit(key="reference_name", limit=get_like_limit, seconds=60 * 60)
def like(reference_doctype: str, reference_name: str, like, route: str = ""):
	like = frappe.parse_json(like)
	ref_doc = get_likeable_doc(reference_doctype, reference_name)
	if ref_doc.disable_likes == 1:
		return

	if like:
		liked = add_like(reference_doctype, reference_name)
	else:
		liked = delete_like(reference_doctype, reference_name)

	# since likes are embedded in the page, clear the web cache
	if route:
		clear_cache(route)

	if like and ref_doc.enable_email_notification:
		ref_doc_title = ref_doc.get_title()
		subject = _("Like on {0}: {1}").format(reference_doctype, ref_doc_title)
		content = _("You have received a ❤️ like on your blog post")
		message = f"<p>{content} <b>{ref_doc_title}</b></p>"
		message = message + "<p><a href='{}/{}#likes' style='font-size: 80%'>{}</a></p>".format(
			frappe.utils.get_request_site_address(), ref_doc.route, _("View Blog Post")
		)

		# notify creator
		frappe.sendmail(
			recipients=frappe.db.get_value("User", ref_doc.owner, "email") or ref_doc.owner,
			subject=subject,
			message=message,
			reference_doctype=ref_doc.doctype,
			reference_name=ref_doc.name,
		)

	return liked


def get_likeable_doc(reference_doctype, reference_name):
	"""Return the published document that can receive likes.

	Missing, unpublished and non-likeable documents all give the same error."""
	try:
		if frappe.get_meta(reference_doctype).has_field("disable_likes"):
			ref_doc = frappe.get_doc(reference_doctype, reference_name)
			if ref_doc.get("published"):
				return ref_doc
	except frappe.DoesNotExistError:
		# drop the "not found" message so it matches the other cases
		frappe.clear_last_message()

	frappe.throw(_("Not permitted"), frappe.PermissionError)


def add_like(reference_doctype, reference_name):
	user = frappe.session.user

	like = frappe.new_doc("Comment")
	like.comment_type = "Like"
	like.comment_email = user
	like.reference_doctype = reference_doctype
	like.reference_name = reference_name
	like.content = "Liked by: " + user
	if user == "Guest":
		like.ip_address = frappe.local.request_ip
	like.save(ignore_permissions=True)
	return True


def delete_like(reference_doctype, reference_name):
	user = frappe.session.user

	filters = {
		"comment_type": "Like",
		"comment_email": user,
		"reference_doctype": reference_doctype,
		"reference_name": reference_name,
	}

	if user == "Guest":
		filters["ip_address"] = frappe.local.request_ip

	frappe.db.delete("Comment", filters)
	return False
