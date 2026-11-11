# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WebCrawlPage(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		error: DF.Data | None
		final_url: DF.Data | None
		html: DF.LongText | None
		meta_tags: DF.JSON | None
		status_code: DF.Int
		text: DF.LongText | None
		title: DF.Data | None
		url: DF.Data | None
		web_crawl: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl Page"


def has_permission(doc, ptype, user=None, debug=False) -> bool:
	from frappe.core.doctype.web_crawl.web_crawl import has_permission as can_access_web_crawl

	web_crawl = frappe.get_cached_doc("Web Crawl", doc.web_crawl)
	return can_access_web_crawl(web_crawl, ptype, user)


def get_permission_query_conditions(user=None) -> str | None:
	user = user or frappe.session.user
	if "System Manager" in frappe.get_roles(user):
		return None
	return f"`tabWeb Crawl Page`.`owner` = {frappe.db.escape(user)}"
