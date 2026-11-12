# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class WebCrawlSource(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		source: DF.Data
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl Source"


def create_web_crawl_sources():
	from frappe.web_crawler.crawler import SOURCES

	for source in SOURCES:
		if not frappe.db.exists("Web Crawl Source", source):
			frappe.get_doc({"doctype": "Web Crawl Source", "source": source}).insert(ignore_permissions=True)
