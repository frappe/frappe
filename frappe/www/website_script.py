# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import strip
from frappe.website.doctype.website_theme.website_theme import get_active_theme

base_template_path = "templates/www/website_script.js"

def get_context(context):
	context.javascript = frappe.db.get_single_value('Website Script',
		'javascript') or ""

	theme = get_active_theme()
	js = strip(theme and theme.js or "")
	if js:
		context.javascript += "\n" + js

	if not frappe.conf.developer_mode:
		context["google_analytics_id"] = (frappe.db.get_single_value("Website Settings", "google_analytics_id")
			or frappe.conf.get("google_analytics_id"))
