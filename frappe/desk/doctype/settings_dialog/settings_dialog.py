# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json
import re

import frappe
from frappe import _
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER, SYSTEM_WRITE_FLAGS
from frappe.model.document import Document

# The address segment a pane or block is opened by: `#settings/<prefix>/<pane>/<block>`.
KEBAB_CASE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")

BINDING_TYPES = ("Single", "Record")
NAME_RESOLVERS = ("session_user",)


class SettingsDialog(Document):
	"""One layer of one app's settings panes; the layers are merged in `frappe.shell.settings`."""

	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.settings_block.settings_block import SettingsBlock
		from frappe.desk.doctype.settings_pane.settings_pane import SettingsPane
		from frappe.types import DF

		app: DF.Autocomplete
		blocks: DF.Table[SettingsBlock]
		extends: DF.Autocomplete
		panes: DF.Table[SettingsPane]
		standard: DF.Check
		user: DF.Link
	# end: auto-generated types

	_DOCTYPE_NAME = "Settings Dialog"

	def autoname(self):
		"""Name a shipped record `<app>` or `<app>-<host>`, since the name is its export path; the rest get a hash."""
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
		self.refuse_panes_on_a_host()
		self.validate_pane_keys()
		self.validate_blocks()
		self.refuse_block_keys_taken_on_the_site()

	def validate_app_content(self):
		"""Only developer mode or a system write may set or clear `standard`, which is app content."""
		if not (self.standard or (not self.is_new() and self.has_value_changed("standard"))):
			return

		if frappe.conf.developer_mode or any(frappe.flags.get(flag) for flag in SYSTEM_WRITE_FLAGS):
			return

		frappe.throw(
			_("{0}'s settings panes belong to its app and can only be authored in developer mode.").format(
				frappe.bold(self.app)
			),
			title=_("Not Editable"),
		)

	def blank_the_host(self):
		"""Clear `extends` outside the app layer: `depends_on` hides the field but does not stop an API write."""
		if not self.standard:
			self.extends = NO_HOST

	def refuse_extending_itself(self):
		if self.extends and self.extends == self.app:
			frappe.throw(
				_("{0} cannot extend its own settings. Add the blocks to its own record instead.").format(
					frappe.bold(self.app)
				),
				title=_("Extends Itself"),
			)

	def refuse_a_second_record_at_this_address(self):
		"""Refuse a second shipped record by name: `db_insert` would read the collision as a hash retry."""
		if not self.is_new() or not self.standard or not frappe.db.exists(self.doctype, self.name):
			return

		frappe.throw(
			_("{0} already ships settings at this address. Edit {1} instead.").format(
				frappe.bold(self.app), frappe.bold(self.name)
			),
			title=_("Already Shipped"),
		)

	def refuse_panes_on_a_host(self):
		"""An app adds blocks to another app's panes, never a pane to another app's group."""
		if self.extends and self.panes:
			frappe.throw(
				_("{0} extends {1}, so it can add blocks to its panes but no pane of its own.").format(
					frappe.bold(self.app), frappe.bold(self.extends)
				),
				title=_("Pane on a Host"),
			)

	def validate_pane_keys(self):
		seen = set()

		for pane in self.panes:
			validate_key(pane.key, _("Pane"), pane.idx)
			if pane.key in seen:
				frappe.throw(
					_("Pane row {0} repeats the key {1}.").format(pane.idx, frappe.bold(pane.key)),
					title=_("Duplicate Key"),
				)
			seen.add(pane.key)

	def validate_blocks(self):
		own_panes = {pane.key for pane in self.panes}
		seen = set()

		for block in self.blocks:
			validate_key(block.key, _("Block"), block.idx)
			if not self.extends and block.pane not in own_panes:
				frappe.throw(
					_("Block row {0} names the pane {1}, which this record does not have.").format(
						block.idx, frappe.bold(block.pane)
					),
					title=_("Unknown Pane"),
				)
			if (block.pane, block.key) in seen:
				frappe.throw(
					_("Block row {0} repeats the key {1} in pane {2}.").format(
						block.idx, frappe.bold(block.key), frappe.bold(block.pane)
					),
					title=_("Duplicate Key"),
				)
			seen.add((block.pane, block.key))
			validate_binding_shape(block)

	def refuse_block_keys_taken_on_the_site(self):
		"""A block key names one block in the merged pane, whichever app ships it."""
		if not self.standard:
			return

		host = self.extends or self.app
		taken = shipped_block_keys(host, exclude=self.name)

		for block in self.blocks:
			if owner := taken.get((block.pane, block.key)):
				frappe.throw(
					_("Block row {0}: {1} already ships a block {2} in pane {3}.").format(
						block.idx, frappe.bold(owner), frappe.bold(block.key), frappe.bold(block.pane)
					),
					title=_("Duplicate Key"),
				)

	def on_update(self):
		self.export_settings_dialog()
		expire_merged_panes()

	def on_trash(self):
		expire_merged_panes()

	def export_settings_dialog(self):
		"""Write this record to `<app>/settings_dialog/<name>/<name>.json`, rooted at the app as `Rail` is."""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_app=self.app)


def expire_merged_panes():
	"""Bump the cached merge's version now, for this transaction, and again once it commits or rolls back."""
	from frappe.shell.settings import bump_panes_version

	bump_panes_version()
	frappe.db.after_commit.add(bump_panes_version)
	frappe.db.after_rollback.add(bump_panes_version)


def validate_key(key: str, kind: str, idx: int):
	if not KEBAB_CASE.match(key or ""):
		frappe.throw(
			_("{0} row {1}: the key {2} must be kebab-case, like {3}.").format(
				kind, idx, frappe.bold(key), frappe.bold("email-accounts")
			),
			title=_("Invalid Key"),
		)


def validate_binding_shape(block):
	"""A block is a generated binding or a component, and each JSON column holds its own shape."""
	if block.binding_type and block.component:
		frappe.throw(
			_("Block row {0} is either a generated binding or a component, not both.").format(block.idx),
			title=_("Invalid Block"),
		)

	if block.binding_type:
		validate_binding(block.idx, block.binding_type, block.document_type, block.name_resolver)
		validate_json_list(block, "fields", str)
	elif block.component:
		validate_named_bindings(block)
		validate_search_settings(block)
	else:
		frappe.throw(
			_("Block row {0} needs a binding type or a component.").format(block.idx),
			title=_("Invalid Block"),
		)

	validate_anchors(block)


def validate_binding(idx: int, binding_type: str, doctype: str, resolver: str | None):
	if binding_type not in BINDING_TYPES or not doctype or not isinstance(doctype, str):
		frappe.throw(
			_("Block row {0}: a binding needs a type ({1}) and a doctype.").format(
				idx, ", ".join(BINDING_TYPES)
			),
			title=_("Invalid Binding"),
		)

	if binding_type == "Record" and resolver not in NAME_RESOLVERS:
		frappe.throw(
			_("Block row {0}: a Record binding names its record with one of: {1}.").format(
				idx, ", ".join(NAME_RESOLVERS)
			),
			title=_("Invalid Binding"),
		)

	if binding_type == "Single" and resolver:
		frappe.throw(
			_("Block row {0}: a Single binding has no name resolver.").format(idx),
			title=_("Invalid Binding"),
		)


def validate_named_bindings(block):
	bindings = parse_json(block, "bindings", {})
	if not isinstance(bindings, dict):
		refuse_json(block, "bindings")

	for binding in bindings.values():
		if not isinstance(binding, dict):
			refuse_json(block, "bindings")
		validate_binding(block.idx, binding.get("type"), binding.get("doctype"), binding.get("resolver"))


def validate_anchors(block):
	"""Each anchor names one block to sit `after` or `before`, and nothing else."""
	validate_json_list(block, "anchors", dict)
	for anchor in parse_json(block, "anchors", []):
		if len(anchor) != 1 or not isinstance(anchor.get("after") or anchor.get("before"), str):
			refuse_json(block, "anchors")


def validate_search_settings(block):
	validate_json_list(block, "settings", dict)
	if not all(isinstance(entry.get("label"), str) for entry in parse_json(block, "settings", [])):
		refuse_json(block, "settings")


def validate_json_list(block, fieldname: str, item_type: type):
	value = parse_json(block, fieldname, [])
	if not isinstance(value, list) or not all(isinstance(item, item_type) for item in value):
		refuse_json(block, fieldname)


def parse_json(block, fieldname: str, default):
	raw = block.get(fieldname)
	if not raw:
		return default

	try:
		return json.loads(raw)
	except ValueError:
		refuse_json(block, fieldname)


def refuse_json(block, fieldname: str):
	frappe.throw(
		_("Block row {0}: {1} does not hold the JSON it should.").format(
			block.idx, frappe.bold(block.meta.get_label(fieldname))
		),
		title=_("Invalid JSON"),
	)


def shipped_block_keys(host: str, exclude: str) -> dict[tuple[str, str], str]:
	"""`(pane, key) -> app` for every block another shipped record puts in this host's panes."""
	records = frappe.get_all(
		"Settings Dialog",
		filters={"standard": 1, "user": SITE_LAYER, "name": ("!=", exclude)},
		or_filters={"extends": host, "app": host},
		fields=["name", "app", "extends"],
	)
	owners = {record.name: record.app for record in records if (record.extends or record.app) == host}
	if not owners:
		return {}

	blocks = frappe.get_all(
		"Settings Block",
		filters={"parenttype": "Settings Dialog", "parent": ("in", list(owners))},
		fields=["parent", "pane", "key"],
	)
	return {(block.pane, block.key): owners[block.parent] for block in blocks}


def on_doctype_update():
	"""One layer per address, held by the schema so a bulk write cannot bypass it."""
	frappe.db.add_unique(
		"Settings Dialog",
		("app", "extends", "user", "standard"),
		constraint_name="unique_settings_dialog_address",
	)
