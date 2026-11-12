# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class WebCrawlResult(Document):
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

	_DOCTYPE_NAME = "Web Crawl Result"
