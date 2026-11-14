# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item.nesting import nesting_errors
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


# A person's or the site's own rows are keyed `user:` or `site:` and six characters; an app's
# shipped key may not start there, or it would read as a row a level added.
RESERVED_KEY_SCOPES = ("user", "site")
RESERVED_KEY_PREFIXES = tuple(f"{scope}:" for scope in RESERVED_KEY_SCOPES)

# A sync from the app's files must not fail a site's migrate for a third-party app's key.
SYNC_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_fixtures")


def validate_item_keys(items, container: str):
	"""Refuse a shipped list with an untyped, keyless, duplicate-keyed or too deeply nested row; both containers call this."""
	seen = set()

	if any(frappe.flags.get(flag) for flag in SYNC_FLAGS):
		drop_reserved_keys(items)

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

		if item.key.startswith(RESERVED_KEY_PREFIXES):
			frappe.throw(
				_("Row {0} has the key {1}, which starts with a prefix a person's own rows use.").format(
					item.idx, frappe.bold(item.key)
				),
				title=_("Reserved Key"),
			)

		if item.key in seen:
			frappe.throw(
				_("Row {0} repeats the key {1}. Two rows with one address cannot both be customized.").format(
					item.idx, frappe.bold(item.key)
				),
				title=_("Duplicate Key"),
			)

		seen.add(item.key)

	if past := nesting_errors(items, container):
		frappe.throw(
			_("{0} sits too deep. A section holds items, and an item holds one more level.").format(
				frappe.bold(", ".join(past))
			),
			title=_("Nested Too Deeply"),
		)


def drop_reserved_keys(items):
	"""Drop, and log, each shipped row whose key a level's own rows use; the rest of the list still loads."""
	for item in [item for item in items if item.key and item.key.startswith(RESERVED_KEY_PREFIXES)]:
		frappe.logger("shell").warning(
			f"Dropped the shipped row {item.key!r}: its key starts with a prefix a person's own rows use."
		)
		items.remove(item)

	for idx, item in enumerate(items, start=1):
		item.idx = idx
