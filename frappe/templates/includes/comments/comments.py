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


def get_limit():
	method = frappe.get_hooks("comment_rate_limit")
	if not method:
		return 5
	else:
		limit = frappe.call(method[0])
		return limit


# `add_comment` moved to frappe.website.api. The aliases keep the old
# dotted paths working; resolved lazily to avoid circular imports.
_MOVED_TO_WEBSITE_API = {
	"add_comment": "add_comment",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_WEBSITE_API.get(name):
		from frappe.website import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
