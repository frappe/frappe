# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.database.utils import drop_index_if_exists
from frappe.desk.doctype.navigation_item.navigation_item import validate_item_keys
from frappe.model.document import Document

# Blank, not `None`: every `NULL` is distinct to the unique index, so a nullable column
# would let one app hold two site layers at one address.
SITE_LAYER = ""

# Blank for the same reason: "extends nobody" has to reach the unique index.
NO_HOST = ""

# The routes by which a shipped rail reaches a site without a person editing it.
SYSTEM_WRITE_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_setup_wizard")


class Rail(Document):
	"""One layer of one app's rail; the layers are resolved into a list at read time, not here."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.navigation_item.navigation_item import NavigationItem
		from frappe.types import DF

		app: DF.Autocomplete
		extends: DF.Autocomplete
		items: DF.Table[NavigationItem]
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	def autoname(self):
		"""Name a shipped rail `<app>` or `<app>-<host>`, since the name is its export path; the rest get a hash."""
		if not self.standard:
			return

		self.name = f"{self.app}-{self.extends}" if self.extends else self.app

	def validate(self):
		self.user = self.user or SITE_LAYER
		self.extends = self.extends or NO_HOST
		self.validate_app_content()
		self.blank_the_host()
		self.refuse_extending_itself()
		self.refuse_a_second_record_at_this_address()
		self.validate_item_keys()

	def blank_the_host(self):
		"""Clear `extends` outside the app layer: `depends_on` hides the field but does not stop an API write."""
		if not self.standard:
			self.extends = NO_HOST

	def refuse_extending_itself(self):
		"""An app extending itself is its own rail written twice."""
		if self.extends and self.extends == self.app:
			frappe.throw(
				_("{0} cannot extend its own rail. Ship the items on its own rail instead.").format(
					frappe.bold(self.app)
				),
				title=_("Extends Itself"),
			)

	def refuse_a_second_record_at_this_address(self):
		"""Refuse a second shipped rail by name: `db_insert` would read the collision as a hash retry."""
		# Needs the name, which `before_insert` runs too early to see.
		if not self.is_new() or not self.standard or not frappe.db.exists("Rail", self.name):
			return

		frappe.throw(
			_("{0} already has a rail at this address. Edit {1} rather than shipping a second.").format(
				frappe.bold(self.app), frappe.bold(self.name)
			),
			title=_("Already Shipped"),
		)

	def validate_app_content(self):
		"""Only developer mode or a system write may set or clear `standard`, which is app content."""
		# On an unsaved document `has_value_changed` is True for every field, hence `is_new()`.
		if not (self.standard or (not self.is_new() and self.has_value_changed("standard"))):
			return

		if frappe.conf.developer_mode:
			return

		if any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_(
				"{0}'s rail belongs to its app and can only be authored in developer mode. "
				"Arrange the rail instead to change it for this site."
			).format(frappe.bold(self.app)),
			title=_("Not Editable"),
		)

	def validate_item_keys(self):
		"""Every row an app ships carries a unique key; only the app layer is checked."""
		if not self.standard:
			return

		validate_item_keys(self.items)

	def on_update(self):
		self.export_rail()

	def export_rail(self):
		"""Write this rail to `<app>/rail/<name>/<name>.json`, rooted at the app since no module owns a rail."""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_app=self.app)


def on_doctype_update():
	"""One layer per address, held by the schema so a bulk write cannot bypass it."""
	# `add_unique` is keyed on the constraint name and skips an existing one, so the old
	# three-column index has to be dropped by name before the wider one can land.
	drop_index_if_exists("tabRail", "unique_layer_address")
	frappe.db.add_unique(
		"Rail", ("app", "extends", "user", "standard"), constraint_name="unique_rail_address"
	)


def has_permission(doc, ptype="read", user=None, debug=False):
	"""A System Manager may read every layer; everyone else only their own."""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""The list-query half of `has_permission`: reports, the API and export go through this."""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return None

	return frappe.qb.DocType("Rail").user == user
