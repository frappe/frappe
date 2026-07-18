# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from contextlib import suppress

import frappe
from frappe import _
from frappe.rate_limiter import rate_limit
from frappe.utils import escape_html, validate_email_address

sitemap = 1


def get_context(context):
	doc = frappe.get_doc("Contact Us Settings", "Contact Us Settings")
	if doc.is_disabled:
		frappe.local.flags.redirect_location = "/404"
		raise frappe.Redirect

	if doc.query_options:
		query_options = [opt.strip() for opt in doc.query_options.replace(",", "\n").split("\n") if opt]
	else:
		query_options = ["Sales", "Support", "General"]

	out = {}
	out.update(doc.as_dict())
	out.update({"query_options": query_options, "parents": [{"name": _("Home"), "route": "/"}]})

	return out


# `send_message` moved to frappe.website.api. The aliases keep the old
# dotted paths working; resolved lazily to avoid circular imports.
_MOVED_TO_WEBSITE_API = {
	"send_message": "send_contact_message",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_WEBSITE_API.get(name):
		from frappe.website import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
