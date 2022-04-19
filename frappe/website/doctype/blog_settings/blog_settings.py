# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
from frappe.model.document import Document


class BlogSettings(Document):
	def on_update(self):
		from frappe.website.render import clear_cache

		clear_cache("blog")
		clear_cache("writers")


def get_feedback_limit():
	return frappe.db.get_single_value("Blog Settings", "feedback_limit") or 0
