# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PageView(Document):
	pass


@frappe.whitelist(allow_guest=True)
def make_view_log(path, referrer=None, browser=None, version=None):
	if path.startswith('/'):
		path = path[1:]

	if is_tracking_enabled():
		view = frappe.new_doc("Page View")
		view.path = path
		view.referrer = referrer
		view.browser = browser
		view.browser_version = version
		view.date = frappe.utils.now_datetime()
		view.insert(ignore_permissions=True)

	return

@frappe.whitelist()
def get_page_view_count(path):
	return frappe.db.count("Page View", filters={'path': path})

def is_tracking_enabled():
	return frappe.db.get_value("Website Settings", "Website Settings", "enable_view_tracking")