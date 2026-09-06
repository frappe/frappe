# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.utils import cint


@frappe.whitelist(allow_guest=True)
def web_search(query: str, scope: str | None = None, limit: int = 20):
	from frappe.search.website_search import WebsiteSearch

	limit = cint(limit)
	ws = WebsiteSearch(index_name="web_routes")
	return ws.search(query, scope, limit)
