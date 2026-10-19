# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe.utils.caching import redis_cache
from frappe.utils.logging import ensure_log_table, get_log_db, log_cutoff, log_table
from frappe.utils.sqlite_document import SQLiteLogDocument


def _log_db():
	"""Return the log database handle, with this DocType's table in place.

	Reads happen before any row of this DocType is written -- the first visitor of a fresh
	site has their uniqueness checked before their view is recorded -- so the table cannot be
	assumed to exist yet. `ensure_log_table` is one-shot per process, so paying for it on
	every read costs a set lookup.
	"""
	ensure_log_table("Web Page View")

	return get_log_db()


class WebPageView(SQLiteLogDocument):
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
		db = get_log_db()
		qb, table = log_table("Web Page View")

		db.sql(qb.from_(table).where(table.creation < log_cutoff(days)).delete())
		db.commit()


# Guests are the subject of this endpoint: an anonymous visitor's page view is the thing
# being counted, so it cannot require a session. The move to the log database leaves that
# exposure unchanged -- every argument is stored as plain data and none is interpolated into
# a query, the path comes from the `Referer` header and is kept only if `is_site_link`
# passes and it is not a desk, API or asset route, and the write is deferred so a caller
# cannot drive one database insert per request.
@frappe.whitelist(allow_guest=True)  # nosemgrep: guest-whitelisted-method
def make_view_log(
	referrer: str | None = None,
	browser: str | None = None,
	version: str | int | None = None,
	user_tz: str | None = None,
	source: str | None = None,
	campaign: str | None = None,
	medium: str | None = None,
	content: str | None = None,
	visitor_id: str | None = None,
):
	if not is_tracking_enabled():
		return

	# real path
	path = frappe.request.headers.get("Referer")

	if not frappe.utils.is_site_link(path):
		return

	path = urlparse(path).path

	request_dict = frappe.request.__dict__
	user_agent = request_dict.get("environ", {}).get("HTTP_USER_AGENT")

	if referrer:
		referrer = referrer.split("?", 1)[0]

	if path != "/" and path.startswith("/"):
		path = path[1:]

	if path.startswith(("api/", "app/", "assets/", "private/files/")):
		return

	# Asked of the log database: this DocType owns no table in the primary one.
	is_unique = visitor_id and not bool(_log_db().exists("Web Page View", {"visitor_id": visitor_id}))

	view = frappe.new_doc("Web Page View")
	view.path = path
	view.referrer = referrer
	view.browser = browser
	view.browser_version = version
	view.time_zone = user_tz
	view.user_agent = user_agent
	view.is_unique = is_unique
	view.source = source
	view.campaign = campaign
	view.medium = (medium or "").lower()
	view.content = content
	view.visitor_id = visitor_id

	try:
		view.deferred_insert()
	except Exception:
		frappe.clear_last_message()


@frappe.whitelist()
@redis_cache(ttl=5 * 60)
def get_page_view_count(path: str):
	return _log_db().count("Web Page View", filters={"path": path})


def is_tracking_enabled():
	return frappe.get_website_settings("enable_view_tracking")
