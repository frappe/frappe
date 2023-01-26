# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib.parse import quote

import frappe
from frappe.model.document import get_controller
from frappe.utils import get_url, nowdate
from frappe.website.router import get_pages

no_cache = 1
base_template_path = "www/sitemap.xml"


def get_context(context):
	"""generate the sitemap XML"""
	links = []

	for route, page in get_pages().items():
		if page.sitemap:
			links.append({"loc": get_url(quote(page.name.encode("utf-8"))), "lastmod": nowdate()})

	for route, data in get_public_pages_from_doctypes().items():
		links.append(
			{
				"loc": get_url(quote((route or "").encode("utf-8"))),
				"lastmod": f"{data['modified']:%Y-%m-%d}",
			}
		)

	return {"links": links}


def get_public_pages_from_doctypes():
	"""Returns pages from doctypes that are publicly accessible"""

	def get_sitemap_routes():
		routes = {}
		doctypes_with_web_view = frappe.get_all(
			"DocType",
			filters={"has_web_view": True, "allow_guest_to_view": True},
			pluck="name",
		)

		for doctype in doctypes_with_web_view:
			controller = get_controller(doctype)
			meta = frappe.get_meta(doctype)
			condition_field = meta.is_published_field or controller.website.condition_field

			if not condition_field:
				continue

			try:
				res = frappe.get_all(
					doctype,
					fields=["route", "name", "modified"],
					filters={condition_field: True},
				)
			except Exception as e:
				if not frappe.db.is_missing_column(e):
					raise e

			for r in res:
				routes[r.route] = {
					"doctype": doctype,
					"name": r.name,
					"modified": r.modified,
				}

		return routes

	return frappe.cache().get_value("sitemap_routes", get_sitemap_routes)
