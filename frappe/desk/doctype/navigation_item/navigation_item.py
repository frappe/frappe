# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

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
