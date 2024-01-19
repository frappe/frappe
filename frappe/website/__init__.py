# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import urlparse

import frappe
import frappe.utils
from frappe.website.doctype.web_page_view.web_page_view import _make_view_log, is_tracking_enabled


@frappe.whitelist(allow_guest=True)
def log_event(
	event_name="WebPageView",  # CamelCase for for compatibility with external platforms?
	referrer=None,
	browser=None,
	version=None,
	user_tz=None,
	source=None,
	campaign=None,
	medium=None,
	visitor_id=None,
	data=None,
):
	"""
	Can be used via /api/method/frappe.website.log_event to log analytical events.

	Implementor's Note: currently, this is backed by an implementation of "Web Page View",
	but inthe future could house a wider variety of events that implements a more fully
	featured analytics platform.

	See also feature writeup: https://github.com/frappe/builder/issues/62
	"""

	if not is_tracking_enabled():  # TODO: ask ankush if this is well-enoughly cached this way?
		return

	# real path
	path = frappe.request.headers.get("Referer")

	if not frappe.utils.is_site_link(path):
		return

	path = urlparse(path).path

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

	if event_name == "WebPageView":
		doc = _make_view_log(
			path=path,
			referrer=referrer,
			browser=browser,
			browser_version=version,
			user_tz=user_tz,
			user_agent=user_agent,
			source=source,
			campaign=campaign,
			medium=medium,
			visitor_id=visitor_id,
			data=data,
		)

	try:
		if frappe.flags.read_only:
			doc.deferred_insert()
		else:
			doc.insert(ignore_permissions=True)
	except Exception:
		frappe.clear_last_message()
