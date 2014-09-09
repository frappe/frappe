# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def get_feed(limit_start, limit_page_length):
	"""get feed"""
	return frappe.get_list("Feed", fields=["name", "feed_type", "doc_type",
		"subject", "owner", "modified", "doc_name", "creation"],
		limit_start = limit_start, limit_page_length = limit_page_length)
