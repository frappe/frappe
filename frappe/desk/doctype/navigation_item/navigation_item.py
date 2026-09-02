# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class NavigationItem(Document):
	"""One row of desk v2 navigation, on the rail or in a sidebar.

	The row holds no behaviour. Everything it does is decided by its `item_type`: the framework
	resolves a row to a destination and a permission bucket by reading the type, so the client
	renders an item without branching on what kind it is, and a type the client has never heard
	of is not a case it has to handle.
	"""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		added: DF.Check
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
		url: DF.Data | None
	# end: auto-generated types

	pass


def validate_item_keys(items):
	"""Refuse a shipped list whose rows are not addressable, one by one.

	A `key` is what every site and user edit is filed against, so a missing or duplicated one
	is not a cosmetic slip: the deltas naming it go inert and the site quietly loses its
	arrangement while the navigation still renders correctly. Navigation that breaks quietly
	gets misdiagnosed as a permission problem, so this fails at write time instead.

	Both containers call it, because both hold these rows and the resolver reads them by key
	from either. Only the app layer is ever checked: a layer's rows are addressed by the base
	key they name, and a row a layer *added* is minted a key when it is written.
	"""
	seen = set()

	for item in items:
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
