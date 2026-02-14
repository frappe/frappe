# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
<<<<<<< HEAD
from frappe.search.full_text_search import FullTextSearch
from frappe.search.sqlite_search import SQLiteSearch
from frappe.search.website_search import WebsiteSearch
=======
>>>>>>> upstream/develop
from frappe.utils import cint


@frappe.whitelist(allow_guest=True)
def web_search(query, scope=None, limit=20):
<<<<<<< HEAD
=======
	from frappe.search.website_search import WebsiteSearch

>>>>>>> upstream/develop
	limit = cint(limit)
	ws = WebsiteSearch(index_name="web_routes")
	return ws.search(query, scope, limit)
