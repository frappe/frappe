# Copyright (c) 2021, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
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

	def validate(self):
		"""Validate workspace link fields"""
		self.validate_card_break()
		self.validate_link_fields()

	def validate_card_break(self):
		"""Card Break doesn't need link_to or link_type"""
		if self.type == "Card Break":
			self.link_to = None
			self.link_type = None
			self.is_query_report = 0

	def validate_link_fields(self):
		"""Ensure link_to is present for non-Card Break types"""
		if self.type != "Card Break" and not self.link_to:
			frappe.throw(
				_("Link To is mandatory for type {0}").format(self.type), title=_("Mandatory Field Missing")
			)
