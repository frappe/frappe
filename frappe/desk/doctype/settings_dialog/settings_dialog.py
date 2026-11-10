# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe import _
from frappe.desk.doctype.rail.rail import NO_HOST, SITE_LAYER, SYSTEM_WRITE_FLAGS
from frappe.desk.settings_block import native_row, upgrade_row
from frappe.desk.settings_records import shipped_records
from frappe.desk.settings_rules import SettingsRules, report
from frappe.model.document import Document


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
		arrangement: DF.JSON | None
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
		self.refuse_what_breaks_a_rule()

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

	def refuse_what_breaks_a_rule(self):
		"""Check every rule against this record and, for a shipped one, against the others in its host's panes."""
		rules = SettingsRules()
		others = shipped_records(self.extends or self.app, exclude=self.name) if self.standard else []
		host = (
			self
			if not self.extends
			else next((r for r in others if r.app == self.extends and not r.extends), None)
		)
		panes = {pane.key for pane in host.panes} if host else None

		problems = [*rules.record_problems(self), *rules.vet(panes, [*others, self]).problems]
		if problem := next((problem for problem in problems if problem.record == self.name), None):
			frappe.throw(problem.message, title=problem.title)

	@staticmethod
	def prepare_for_import(docdict):
		"""Read a file in either shape: the old one (no `kind`, a component's `fields` and `settings`) or native JSON columns."""
		docdict["blocks"] = [upgrade_row(block) for block in docdict.get("blocks") or []]
		if isinstance(docdict.get("arrangement"), dict):
			docdict["arrangement"] = json.dumps(docdict["arrangement"])

	def before_import(self):
		"""Migrate imports a shipped record without `validate`: check what needs only this record."""
		rules = SettingsRules()
		panes = None if self.extends else {pane.key for pane in self.panes}
		problems = [*rules.record_problems(self), *rules.vet(panes, [self]).problems]
		report([problem for problem in problems if not problem.across])

	def on_update(self):
		self.export_settings_dialog()

	def before_export(self, doc_export):
		"""Write each block's JSON columns, and the arrangement, as native JSON, which `prepare_for_import` turns back into text."""
		if arrangement := doc_export.get("arrangement"):
			doc_export["arrangement"] = json.loads(arrangement) if isinstance(arrangement, str) else arrangement
		doc_export["blocks"] = [native_row(block) for block in doc_export["blocks"]]

	def export_settings_dialog(self):
		"""Write this record to `<app>/settings_dialog/<name>/<name>.json`, rooted at the app as `Rail` is."""
		from frappe.modules.export_file import export_to_files

		if not self.standard or frappe.flags.in_import or not frappe.conf.developer_mode:
			return

		export_to_files(record_list=[[self.doctype, self.name]], record_app=self.app)


def on_doctype_update():
	"""One layer per address, held by the schema so a bulk write cannot bypass it."""
	frappe.db.add_unique(
		"Settings Dialog",
		("app", "extends", "user", "standard"),
		constraint_name="unique_settings_dialog_address",
	)
