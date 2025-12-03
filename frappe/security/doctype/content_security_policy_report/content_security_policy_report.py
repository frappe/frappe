# Copyright (c) 2025, Frappe Technologies and contributors
# For license information, please see license.txt

# import frappe
from frappe.model.document import Document


class ContentSecurityPolicyReport(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		blocked_url: DF.Data | None
		column_number: DF.Int
		disposition: DF.Data | None
		document_url: DF.Data | None
		effective_directive: DF.Data | None
		line_number: DF.Int
		original_policy: DF.Data | None
		referrer: DF.Data | None
		sample: DF.Data | None
		source_file: DF.Data | None
		status_code: DF.Int
		url: DF.Data | None
		user_agent: DF.Data | None
	# end: auto-generated types

	pass
