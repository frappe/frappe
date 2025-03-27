# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

# import frappe
from frappe.model.document import Document


class WorkspaceLink(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dependencies: DF.Data | None
		description: DF.HTMLEditor | None
		hidden: DF.Check
		icon: DF.Data | None
		is_query_report: DF.Check
		label: DF.Data
		link_count: DF.Int
		link_to: DF.DynamicLink | None
		link_type: DF.Literal["DocType", "Page", "Report"]
		onboard: DF.Check
		only_for: DF.Link | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		report_ref_doctype: DF.Link | None
		type: DF.Literal["Link", "Card Break"]
	# end: auto-generated types

	pass
