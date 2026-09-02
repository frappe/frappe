# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.database.utils import drop_index_if_exists
from frappe.desk.doctype.navigation_item.navigation_item import validate_item_keys
from frappe.model.document import Document

# Blank, not `None`: the column is not nullable so that one spelling of "not a user's own layer"
# reaches the index. Every `NULL` is distinct to an index, so a nullable column would let one app
# hold two site layers that both look like one address.
SITE_LAYER = ""

# Blank, for the same reason and read the same way: "this layer extends nobody, it is the app's
# own rail". A nullable column would not reach the unique index below.
NO_HOST = ""

# The writes that are an app's content arriving on a site rather than a person editing it. Each is
# a real route by which a shipped rail reaches a site, and without them, installing or updating an
# app that ships one would fail on every customer site.
SYSTEM_WRITE_FLAGS = ("in_install", "in_patch", "in_migrate", "in_import", "in_setup_wizard")


class Rail(Document):
	"""One layer of one app's rail.

	The document holds the layer; how they resolve into the list a person sees is not
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
		extends: DF.Autocomplete
		items: DF.Table[NavigationItem]
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	def autoname(self):
		"""Name a shipped rail after what it arranges; everything else gets a hash.

		The export path requires it, because the record name is the file path. A hash-named
		standard record would write `<app>/rail/6a1f9c2e/6a1f9c2e.json`, and a re-export from a
		fresh bench would create a second file, leaving the first as a permanent orphan.

		An app ships more than one of these once it extends somebody: its own rail, plus a record
		per host. So the name is the address and not the app alone — `telephony` for its own,
		`telephony-erpnext` for what it adds to ERPNext's. A hyphen separates them because an app
		name is a Python module name and can never contain one.

		An opaque name costs the other two layers nothing, because a layer is looked up by filter
		and never by name.
		"""
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
		"""Clear `extends` outside the app layer, because extending is an app-layer claim.

		`depends_on` hides the field on the two writable layers but does not stop an API write, and
		a site or user row naming a host would be one person's arrangement of a rail they do not
		own — which is also the row that already exists, since a person arranges a host rail
		through the host's own address and gets every contributed item in the same list.
		"""
		if not self.standard:
			self.extends = NO_HOST

	def refuse_extending_itself(self):
		"""An app extending itself is its own rail written twice, and the two would both merge.

		Cheap to state and impossible to mean: the second record would be appended to the first
		with its keys namespaced `<app>:<key>`, so every item would appear once addressable and
		once not.
		"""
		if self.extends and self.extends == self.app:
			frappe.throw(
				_("{0} cannot extend its own rail. Ship the items on its own rail instead.").format(
					frappe.bold(self.app)
				),
				title=_("Extends Itself"),
			)

	def refuse_a_second_record_at_this_address(self):
		"""Say plainly that a shipped rail is already there, rather than letting the insert fail.

		The unique index below is the guarantee and stays the guarantee — it holds against a bulk
		write and against anything that skips the document. This is about the message. A shipped
		rail's name *is* its address, while the doctype autonames by `hash` for the sake of the
		other two layers, so `db_insert` reads the primary-key collision as a hash collision and
		retries. `autoname` puts the same name back each time, so it retries five times and then
		re-raises the driver's own `IntegrityError`, which names a column and no cause.

		Only shipped rows have a deterministic name, so only they can reach that path. Everything
		else keeps its hash and meets the index, which reports itself properly.

		In `validate` rather than `before_insert`, which runs before the name exists: `insert`
		calls `before_insert`, then `set_new_name`, then the before-save methods.
		"""
		if not self.is_new() or not self.standard or not frappe.db.exists("Rail", self.name):
			return

		frappe.throw(
			_("{0} already has a rail at this address. Edit {1} rather than shipping a second.").format(
				frappe.bold(self.app), frappe.bold(self.name)
			),
			title=_("Already Shipped"),
		)

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
		"""The shared rule, in `navigation_item.py`: an app's rows must each carry a unique key.

		Only the app layer is checked. A layer's rows are addressed by the base key they name,
		and a row the layer *added* is minted a key on export alongside the rest.
		"""
		if not self.standard:
			return

		validate_item_keys(self.items)

	def on_update(self):
		self.export_rail()

	def export_rail(self):
		"""Write this rail to its file, so authoring it and shipping it are one step.

		The path is `<app>/rail/<name>/<name>.json`: the usual per-record folder, rooted at the app
		instead of a module, because no module owns a rail. The import walk and the orphan sweep
		both work on that shape unchanged, because the filename and the record name agree — which
		is why `autoname` makes the name the address, so an app that extends two hosts writes three
		files rather than overwriting one.
		"""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_app=self.app)


def on_doctype_update():
	"""Enforce one layer per address in the schema rather than in a `validate` hook.

	A hook is bypassed by `db_insert`, a bulk write, or anything that skips the document, and two
	documents at one address would give the merge two answers for the same layer.

	The index is composite because an address is four columns. `user` alone would let one person
	arrange only one app's rail. `standard` is in it because an app's own rail and the site's
	arrangement of it are two documents at the same `(app, user)`: one shipped, one curated, and
	resetting the site's must not touch the app's. `extends` is in it because an app ships one
	record per rail it joins and one for its own, and the three-column form made extending
	unstorable rather than merely unresolvable: `telephony` already owns `(telephony, "", 1)`, so
	its second record collided with its first.

	The old three-column index is dropped by name. `add_unique` is keyed on the constraint name
	and does nothing when one already exists, so widening the columns under the same name would
	have been a silent no-op on every bench that has already migrated this branch.
	"""
	drop_index_if_exists("tabRail", "unique_layer_address")
	frappe.db.add_unique(
		"Rail", ("app", "extends", "user", "standard"), constraint_name="unique_rail_address"
	)


def has_permission(doc, ptype="read", user=None, debug=False):
	"""Allow a System Manager to curate the site and the apps; everyone else gets only their own.

	This is the document-level half of the gate the endpoints hold. A `Desk User` has `read` and
	nothing more: rearranging a rail goes through an endpoint that writes one person's own layer
	with `ignore_permissions`, so no write permission is needed or granted. This stops the read
	they do have from being a read of everyone else's layers.

	`System Manager`, not `Workspace Manager`: this table is not about workspaces, and `Sidebar`,
	the other container desk v2 uses, has always granted `System Manager` and has never had a
	`Workspace Manager` row. Reaching for the narrower role here made the branch disagree with
	itself about who may curate. The cost is real and accepted: curating the site layer can no
	longer be delegated without full site administration.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return True

	return bool(doc.user) and doc.user == user


def get_permission_query_conditions(user=None):
	"""Restrict list queries so everyone but a System Manager sees only their own layer.

	This pairs with `has_permission` and is not redundant: reports, the API and the desk's export
	go through this rather than through the document-level check.

	Returns a query-builder term rather than a SQL string. The hook accepts either -- `query.py`
	wraps a string in a `RawCriterion` and lets a term through as it is -- and the term keeps the
	identifier quoting out of this file, which a hand-written `` `tabRail` `` spells the way only
	MySQL accepts. The sidebar's two older hooks still build strings; they are desk v1's and are
	left alone.
	"""
	user = user or frappe.session.user
	if user == "Administrator" or "System Manager" in frappe.get_roles(user):
		return None

	return frappe.qb.DocType("Rail").user == user
