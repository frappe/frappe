# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document

MUST_BE_POSITIVE = (
	"max_pages",
	"max_crawl_time",
	"page_timeout",
	"max_page_size",
	"sitemap_timeout",
	"max_sitemap_size",
)


class WebCrawlerSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.web_crawler_blocked_domain.web_crawler_blocked_domain import (
			WebCrawlerBlockedDomain,
		)
		from frappe.types import DF

		blocked_domains: DF.Table[WebCrawlerBlockedDomain]
		max_crawl_time: DF.Int
		max_depth: DF.Int
		max_page_size: DF.Int
		max_pages: DF.Int
		max_redirects: DF.Int
		max_sitemap_size: DF.Int
		page_timeout: DF.Int
		request_delay: DF.Float
		respect_robots_txt: DF.Check
		sitemap_timeout: DF.Int
		user_agent: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawler Settings"

	def validate(self):
		for fieldname in MUST_BE_POSITIVE:
			if self.get(fieldname) <= 0:
				label = _(self.meta.get_label(fieldname))
				frappe.throw(_("{0} must be greater than 0.").format(label), title=_("Invalid value"))
