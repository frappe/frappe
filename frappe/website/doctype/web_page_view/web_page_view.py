# Copyright (c) 2020, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe.model.document import Document


class WebPageView(Document):
	pass


@frappe.whitelist(allow_guest=True)
def make_view_log(path, referrer=None, browser=None, version=None, url=None, user_tz=None):
	if not is_tracking_enabled():
		return

	request_dict = frappe.request.__dict__
	user_agent = request_dict.get("environ", {}).get("HTTP_USER_AGENT")

	if referrer:
		referrer = referrer.split("?", 1)[0]

	is_unique = True
	if referrer.startswith(url):
		is_unique = False

	if path != "/" and path.startswith("/"):
		path = path[1:]

	view = frappe.new_doc("Web Page View")
	view.path = path
	view.referrer = referrer
	view.browser = browser
	view.browser_version = version
	view.time_zone = user_tz
	view.user_agent = user_agent
	view.is_unique = is_unique

	try:
		if frappe.flags.read_only:
			view.deferred_insert()
		else:
			view.insert(ignore_permissions=True)
	except Exception:
		if frappe.message_log:
			frappe.message_log.pop()


@frappe.whitelist()
def get_page_view_count(path):
	return frappe.db.count("Web Page View", filters={"path": path})


def is_tracking_enabled():
	return frappe.db.get_single_value("Website Settings", "enable_view_tracking")
