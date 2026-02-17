# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.search.full_text_search import FullTextSearch
from frappe.search.sqlite_search import SQLiteSearch
from frappe.search.website_search import WebsiteSearch
from frappe.utils import cint


@frappe.whitelist(allow_guest=True)
<<<<<<< HEAD
def web_search(query, scope=None, limit=20):
=======
def web_search(query: str, scope: str | None = None, limit: int = 20):
	from frappe.search.website_search import WebsiteSearch

>>>>>>> 9eef4f6dae (fix: force type check in whitelisted methods (#37044))
	limit = cint(limit)
	ws = WebsiteSearch(index_name="web_routes")
	return ws.search(query, scope, limit)
