# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.desk.doctype.workspace.workspace import is_workspace_manager
from frappe.model.document import Document

# Blank, not `None`: the column is not nullable so that one spelling of "not a user's own layer"
# reaches the index. Every `NULL` is distinct to an index, so a nullable column would let one app
# hold two site layers that both look like one address.
SITE_LAYER = ""

# The writes that are an app's content arriving on a site rather than a person editing it. Each is
# a real route by which a shipped rail reaches a site, and without them, installing or updating an
# app that ships one would fail on every customer site.
SYSTEM_WRITE_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_setup_wizard")


class Rail(Document):
	"""One layer of one app's rail.

	The document holds the layer; how three of them resolve into the list a person sees is not
	here. That resolution is one engine shared with the sidebar -- the rail and the sidebar are two
	presentations of one model, not two models -- and it runs at read time, against the whole of a
	prefix, on the way into boot.
	"""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.navigation_item.navigation_item import NavigationItem
		from frappe.types import DF

		app: DF.Autocomplete
		items: DF.Table[NavigationItem]
		mount_on: DF.Autocomplete | None
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	def autoname(self):
		"""Name an app's own rail after the app; everything else gets a hash.

		The export path requires it, because the record name is the file path. A hash-named
		standard record would write `<app>/rail/6a1f9c2e/6a1f9c2e.json`, and a re-export from a
		fresh bench would create a second file, leaving the first as a permanent orphan.

		An opaque name costs the other two layers nothing, because a layer is looked up by filter
		and never by name.
		"""
		if self.standard:
			self.name = self.app

	def validate(self):
		self.user = self.user or SITE_LAYER
		self.validate_app_content()
		self.blank_the_mount()
		self.validate_item_keys()

	def blank_the_mount(self):
		"""Clear `mount_on` outside the app layer, because mounting is an app-layer claim.

		`depends_on` hides the field on the two writable layers but does not stop an API write, and
		a site row carrying a mount would put a user's arrangement on another app's rail.
		"""
		if not self.standard:
			self.mount_on = None

	def validate_app_content(self):
		"""Allow only developer mode to set or clear the standard flag, because it is app content.

		Conditional rather than blanket: all three layers live in one table, and the site's and
		each person's rows have to stay writable at runtime. With no guard at all, a Workspace
		Manager could take an app's row, clear the flag, and turn git-versioned app content into a
		site row they own.

		The `is_new()` check matters: on an unsaved document `has_value_changed` returns True for
		every field, so without it every site- and user-layer row would be refused outside
		developer mode.
		"""
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
		"""Refuse a shipped rail whose rows are not addressable, one by one.

		A `key` is what every site and user edit is filed against, so a missing or duplicated one
		is not a cosmetic slip: the deltas naming it go inert and the site quietly loses its
		arrangement while the rail still renders correctly. Navigation that breaks quietly gets
		misdiagnosed as a permission problem, so this fails at write time instead.

		Only the app layer is checked. A layer's rows are addressed by the base key they name, and
		a row the layer *added* is minted a key on export alongside the rest.
		"""
		if not self.standard:
			return

		seen = set()
		for item in self.items:
			if not item.key:
				frappe.throw(
					_("Row {0} ({1}) has no key. Every item an app ships needs one, frozen for good.").format(
						item.idx, frappe.bold(item.label or item.link_to or item.item_type)
					),
					title=_("Missing Key"),
				)

			if item.key in seen:
				frappe.throw(
					_(
						"Row {0} repeats the key {1}. Two rows with one address cannot both be customized."
					).format(item.idx, frappe.bold(item.key)),
					title=_("Duplicate Key"),
				)

			seen.add(item.key)

	def on_update(self):
		self.export_rail()

	def export_rail(self):
		"""Write this rail to its file, so authoring it and shipping it are one step.

		The path is `<app>/rail/<app>/<app>.json`: the usual per-record folder, rooted at the app
		instead of a module, because an app has one rail and no module owns it. The import walk and
		the orphan sweep both work on that shape unchanged, because the filename and the record
		name agree.
		"""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_app=self.app)


def on_doctype_update():
	"""Enforce one layer per address in the schema rather than in a `validate` hook.

	A hook is bypassed by `db_insert`, a bulk write, or anything that skips the document, and two
	documents at one address would give the merge two answers for the same layer.

	The index is composite because an address is three columns. `user` alone would let one person
	arrange only one app's rail. `standard` is in it because an app's own rail and the site's
	arrangement of it are two documents at the same `(app, user)`: one shipped, one curated, and
	resetting the site's must not touch the app's.
	"""
	frappe.db.add_unique("Rail", ("app", "user", "standard"), constraint_name="unique_layer_address")


def has_permission(doc, ptype="read", user=None, debug=False):
	"""Allow a Workspace Manager to curate the site and the apps; everyone else gets only their own.

	This is the document-level half of the gate the endpoints hold. A `Desk User` has `read` and
	nothing more: rearranging a rail goes through an endpoint that writes one person's own layer
	with `ignore_permissions`, so no write permission is needed or granted. This stops the read
	they do have from being a read of everyone else's layers.

	The manager check is the same one the sidebar's layers use. A second role for "may rearrange
	what everyone sees" would be two ways to grant one capability.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Restrict list queries so everyone but a Workspace Manager sees only their own layer.

	This pairs with `has_permission` and is not redundant: reports, the API and the desk's export
	go through this rather than through the document-level check.

	Returns a query-builder term rather than a SQL string. The hook accepts either -- `query.py`
	wraps a string in a `RawCriterion` and lets a term through as it is -- and the term keeps the
	identifier quoting out of this file, which a hand-written `` `tabRail` `` spells the way only
	MySQL accepts. The sidebar's two older hooks still build strings; they are desk v1's and are
	left alone.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or is_workspace_manager(user):
		return None

	return frappe.qb.DocType("Rail").user == user
