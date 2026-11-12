# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WebCrawlSourceItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		source: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "Web Crawl Source Item"
