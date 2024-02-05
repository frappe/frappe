# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

from urllib import robotparser
from urllib.parse import quote

import frappe
from frappe.model.document import get_controller
from frappe.utils import get_url, nowdate
from frappe.utils.caching import redis_cache
from frappe.website.router import get_doctypes_with_web_view, get_pages

no_cache = 1
base_template_path = "www/sitemap.xml"


def get_context(context):
	"""generate the sitemap XML"""
	links = [
		{"loc": get_url(quote(page.name.encode("utf-8"))), "lastmod": nowdate()}
		for route, page in get_pages().items()
		if page.sitemap
	]

	links.extend(
		{
			"loc": get_url(quote((route or "").encode("utf-8"))),
			"lastmod": f"{data['modified']:%Y-%m-%d}",
		}
		for route, data in get_public_pages_from_doctypes().items()
	)

	return {"links": links}


@redis_cache()
def get_public_pages_from_doctypes():
	"""Return pages from doctypes that are publicly accessible."""

	def get_sitemap_routes():
		routes = {}
		doctypes_with_web_view = get_doctypes_with_web_view()
		rp = None
		if robots_txt := frappe.db.get_single_value("Website Settings", "robots_txt"):
			rp = robotparser.RobotFileParser()
			rp.parse(robots_txt.splitlines())

		for doctype in doctypes_with_web_view:
			controller = get_controller(doctype)
			meta = frappe.get_meta(doctype)
			if not meta.allow_guest_to_view:
				continue

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
				if rp and not rp.can_fetch("*", f"/{r.route}"):
					continue

				routes[r.route] = {
					"doctype": doctype,
					"name": r.name,
					"modified": r.modified,
				}

		return routes

	return get_sitemap_routes()
