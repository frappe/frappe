# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe.model.document import Document
from frappe.utils.caching import redis_cache


class WebPageView(Document):
	_DOCTYPE_NAME = "Web Page View"

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		browser: DF.Data | None
		browser_version: DF.Data | None
		campaign: DF.Data | None
		content: DF.Data | None
		is_unique: DF.Data | None
		medium: DF.Data | None
		path: DF.Data | None
		referrer: DF.Data | None
		source: DF.Data | None
		time_zone: DF.Data | None
		user_agent: DF.Data | None
		visitor_id: DF.Data | None
	# end: auto-generated types

	@staticmethod
	def clear_old_logs(days=180):
		from frappe.query_builder import Interval
		from frappe.query_builder.functions import Now

		table = frappe.qb.DocType("Web Page View")
		frappe.db.delete(table, filters=(table.creation < (Now() - Interval(days=days))))


def is_tracking_enabled():
	return frappe.get_website_settings("enable_view_tracking")


# `make_view_log`, `get_page_view_count` moved to frappe.website.api. The aliases keep the old
# dotted paths working; resolved lazily to avoid circular imports.
_MOVED_TO_WEBSITE_API = {
	"make_view_log": "make_view_log",
	"get_page_view_count": "get_page_view_count",
}


def __getattr__(name: str):
	if new_name := _MOVED_TO_WEBSITE_API.get(name):
		from frappe.website import api

		return getattr(api, new_name)
	raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
