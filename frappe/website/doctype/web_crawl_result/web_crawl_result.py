# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document
from frappe.website.doctype.web_crawl.web_crawl import has_permission as can_read_web_crawl
from frappe.website.doctype.web_crawl.web_crawl import owner_condition


class WebCrawlResult(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		description: DF.SmallText | None
		error: DF.Data | None
		final_url: DF.SmallText | None
		html: DF.LongText | None
		meta_tags: DF.JSON | None
		status_code: DF.Int
		text: DF.LongText | None
		title: DF.SmallText | None
		url: DF.SmallText | None
		web_crawl: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl Result"


def has_permission(
	doc: WebCrawlResult, ptype: str | None = None, user: str | None = None, debug=False
) -> bool:
	return can_read_web_crawl(frappe.get_doc("Web Crawl", doc.web_crawl), ptype, user)


def get_permission_query_conditions(user: str | None = None) -> str | None:
	return owner_condition("Web Crawl Result", user)
