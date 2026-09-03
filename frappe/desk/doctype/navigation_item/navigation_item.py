# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class NavigationItem(Document):
	"""One row of desk v2 navigation, on the rail or in a sidebar; its `item_type` decides everything it does."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added: DF.Check
		anchors: DF.Code | None
		collapsible: DF.Check
		hidden: DF.Check
		icon: DF.Icon | None
		item_type: DF.Link
		keep_closed: DF.Check
		key: DF.Data | None
		label: DF.Data | None
		link_doctype: DF.Link | None
		link_to: DF.DynamicLink | None
		overrides: DF.Code | None
		parent: DF.Data
		parent_key: DF.Data | None
		parentfield: DF.Data
		parenttype: DF.Data
		payload: DF.Code | None
		switches_app: DF.Check
		url: DF.Data | None
	# end: auto-generated types

	def validate(self):
		self.validate_type_on_an_item()

	def validate_type_on_an_item(self):
		"""An added row is the item and names its type; `item_type` is not `reqd` because a delta row has none."""
		if self.added and not self.item_type:
			frappe.throw(
				_("Row {0} adds an item but does not say what kind. An added row is the item.").format(
					self.idx
				),
				title=_("Missing Type"),
			)


def validate_item_keys(items):
	"""Refuse a shipped list with an untyped, keyless or duplicate-keyed row; both containers call this."""
	seen = set()

	for item in items:
		if not item.item_type:
			frappe.throw(
				_("Row {0} does not say what kind of item it is.").format(item.idx),
				title=_("Missing Type"),
			)

		if not item.key:
			frappe.throw(
				_("Row {0} ({1}) has no key. Every item an app ships needs one, frozen for good.").format(
					item.idx, frappe.bold(item.label or item.link_to or item.item_type)
				),
				title=_("Missing Key"),
			)

		if item.key in seen:
			frappe.throw(
				_("Row {0} repeats the key {1}. Two rows with one address cannot both be customized.").format(
					item.idx, frappe.bold(item.key)
				),
				title=_("Duplicate Key"),
			)

		seen.add(item.key)
