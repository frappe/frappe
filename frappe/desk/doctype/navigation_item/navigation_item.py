# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import frappe
from frappe import _
from frappe.desk.doctype.navigation_item.links import default_new_tab
from frappe.model.document import Document
from frappe.utils import get_url

VIEW = "view"
DOCTYPE = "doctype"
LINK = "link"

BUILT_IN_TYPES = (VIEW, DOCTYPE, LINK)

REQUIRED_FIELDS = {VIEW: ("view",), DOCTYPE: ("label", "dt"), LINK: ("label", "url")}


class NavigationItem(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		dt: DF.Link | None
		hidden: DF.Check
		icon: DF.Data | None
		label: DF.Data | None
		new_tab: DF.Check
		overrides: DF.Data | None
		parent: DF.Data
		parentfield: DF.Data
		parenttype: DF.Data
		type: DF.Literal["view", "doctype", "link"]
		url: DF.Data | None
		view: DF.Link | None
	# end: auto-generated types

	def validate_item(self, stored=None):
		"""Validate this row against `stored`, the version it is replacing."""
		if self.overrides:
			return
		self.type = self.type or VIEW
		self.validate_required_fields()
		self.validate_listable()
		self.set_new_tab(stored)

	def validate_required_fields(self):
		"""Require the fields this row's type needs; an app-added type answers for its own."""
		missing = [field for field in REQUIRED_FIELDS.get(self.type, ()) if not self.get(field)]
		if missing:
			frappe.throw(
				_("A {0} item needs {1}.").format(self.type, ", ".join(missing)),
				frappe.MandatoryError,
			)

	def validate_listable(self):
		"""Refuse a doctype with no list for an item to navigate to."""
		if self.type != DOCTYPE:
			return

		meta = frappe.db.get_value("DocType", self.dt, ["issingle", "istable"], as_dict=True)
		if meta and (meta.issingle or meta.istable):
			frappe.throw(_("{0} has no list to open.").format(self.dt), frappe.ValidationError)

	def set_new_tab(self, stored):
		"""Follow the URL, unless somebody has said otherwise."""
		if stored and stored.url == self.url:
			return
		if stored and stored.new_tab != default_new_tab(stored.url, get_url()):
			return
		self.new_tab = default_new_tab(self.url, get_url())
