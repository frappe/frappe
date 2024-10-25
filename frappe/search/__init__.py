# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.search.full_text_search import FullTextSearch
from frappe.search.website_search import WebsiteSearch
from frappe.utils import cint


@frappe.whitelist(allow_guest=True)
def web_search(query, scope=None, limit: int = 20):
	limit = cint(limit)
	ws = WebsiteSearch(index_name="web_routes")
	return ws.search(query, scope, limit)
