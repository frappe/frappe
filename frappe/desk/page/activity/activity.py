# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: See license.txt

from __future__ import unicode_literals
import frappe

@frappe.whitelist()
def get_feed(limit_start, limit_page_length):
	"""get feed"""
	return frappe.get_list("Feed", fields=["name", "feed_type", "doc_type",
		"subject", "owner", "modified", "doc_name", "creation"],
		limit_start = limit_start, limit_page_length = limit_page_length,
		order_by="creation desc")

@frappe.whitelist()
def get_months_activity():
	return frappe.db.sql("""select date(creation), count(name)
		from `tabFeed` where date(creation) > subdate(curdate(), interval 1 month)
		group by date(creation)
		order by creation asc""", as_list=1)
