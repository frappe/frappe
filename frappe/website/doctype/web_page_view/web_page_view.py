# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class WebPageView(Document):
	pass


@frappe.whitelist(allow_guest=True)
def make_view_log(path, referrer=None, browser=None, version=None, url=None, user_tz=None):
	request_dict = frappe.request.__dict__
	user_agent = request_dict.get('environ', {}).get('HTTP_USER_AGENT')

	is_unique = True
	if referrer.startswith(url):
		is_unique = False

	if path != "/" and path.startswith('/'):
		path = path[1:]

	if is_tracking_enabled():
		view = frappe.new_doc("Web Page View")
		view.path = path
		view.referrer = referrer
		view.browser = browser
		view.browser_version = version
		view.time_zone = user_tz
		view.user_agent = user_agent
		view.is_unique = is_unique
		view.insert(ignore_permissions=True)

	return

@frappe.whitelist()
def get_page_view_count(path):
	return frappe.db.count("Web Page View", filters={'path': path})

def is_tracking_enabled():
	return frappe.db.get_value("Website Settings", "Website Settings", "enable_view_tracking")