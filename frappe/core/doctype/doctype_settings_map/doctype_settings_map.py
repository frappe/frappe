# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import os

import frappe
from frappe import _
from frappe.model.document import Document


class DocTypeSettingsMap(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.core.doctype.doctype_settings_map_item.doctype_settings_map_item import (
			DocTypeSettingsMapItem,
		)
		from frappe.types import DF

		applies_to_doctype: DF.Link
		is_active: DF.Check
		is_standard: DF.Check
		mappings: DF.Table[DocTypeSettingsMapItem]
		module: DF.Link | None
	# end: auto-generated types

	def before_naming(self):
		self._set_default_module()

	def _set_default_module(self):
		# Standard maps ship with an app; default the owning module to the one that owns the
		# doctype they apply to (the dev can override). Custom maps aren't exported.
		if self.is_standard and not self.module:
			self.module = frappe.db.get_value("DocType", self.applies_to_doctype, "module")

	def autoname(self):
		# Name the record after the doctype it applies to. A doctype may have both a custom
		# and a standard map, which can't share a name — the custom (user-created) one keeps
		# the plain doctype name; the standard one is keyed by its module.
		self.name = self.applies_to_doctype
		if self.is_standard:
			self.name = f"{self.applies_to_doctype} - {self.module}"

	def validate(self):
		self._guard_standard()
		self._set_default_module()
		self._validate_unique_per_doctype()

	def on_update(self):
		self._enforce_single_active()
		self.export_doc()

	def export_doc(self):
		"""Write standard maps to `<module>/doctype_settings_map/<applies_to_doctype>.json`
		(developer mode only) — one flat file per doctype, so they ship in code and sync on
		migrate. Custom maps (is_standard=0) are a no-op and stay in the site DB."""
		if frappe.flags.in_import or not self.is_standard or not frappe.conf.developer_mode:
			return

		from frappe.modules.export_file import strip_default_fields

		doc_export = self.as_dict(no_nulls=True, ignore_computed_child_tables=True)
		self.run_method("before_export", doc_export)
		doc_export = strip_default_fields(self, doc_export)

		path = self.get_export_path()
		frappe.create_folder(os.path.dirname(path))
		with open(path, "w+") as f:  # nosemgrep
			f.write(frappe.as_json(doc_export) + "\n")

		return path

	def get_export_path(self) -> str:
		from frappe.modules.utils import get_module_path

		return os.path.join(
			get_module_path(self.module),
			"doctype_settings_map",
			f"{frappe.scrub(self.applies_to_doctype)}.json",
		)

	def on_trash(self):
		self._guard_standard()
		# If the active map is being deleted, promote the remaining one (prefer standard).
		if self.is_active:
			self._set_sibling_active()
		# Drop the shipped JSON too, else the next migrate re-imports the deleted map. Never
		# during migrate/install/patch: a cleanup patch deleting stale records must not take
		# the app's shipped files with it.
		if (
			self.is_standard
			and frappe.conf.developer_mode
			and not frappe.flags.in_test
			and not (frappe.flags.in_migrate or frappe.flags.in_install or frappe.flags.in_patch)
		):
			frappe.db.after_commit(self.delete_export_file)

	def delete_export_file(self):
		path = self.get_export_path()
		if os.path.exists(path):
			os.remove(path)

	def _guard_standard(self):
		"""Standard maps are shipped with an app — only editable in Developer Mode.

		Migrate/install are exempt so shipped fixtures can sync. Custom maps (is_standard=0)
		are user-editable under normal permissions."""
		if not self.is_standard:
			return
		if frappe.conf.developer_mode or frappe.flags.in_migrate or frappe.flags.in_install:
			return
		frappe.throw(
			_("Standard DocType Settings Map can only be changed in Developer Mode."),
			frappe.PermissionError,
		)

	def _validate_unique_per_doctype(self):
		"""One standard map per (module, doctype), and one custom map per doctype."""
		filters = {
			"applies_to_doctype": self.applies_to_doctype,
			"is_standard": self.is_standard,
			"name": ("!=", self.name),
		}
		if self.is_standard:
			filters["module"] = self.module

		if frappe.db.exists("DocType Settings Map", filters):
			if self.is_standard:
				frappe.throw(
					_("A standard settings map already exists for {0} in {1}.").format(
						self.applies_to_doctype, self.module
					)
				)
			frappe.throw(_("A custom settings map already exists for {0}.").format(self.applies_to_doctype))

	def _enforce_single_active(self):
		"""Only one map per doctype may be active — standard or custom.

		Sibling toggles use `db.set_value` so they bypass the standard dev-lock guard: a user
		activating their custom map (which they may edit) deactivates the standard, and
		deactivating it again falls back to the standard — without ever writing the standard
		record directly through the controller."""
		if self.is_active:
			# Canonical "only one default" idiom: unset the flag on all other maps for this
			# doctype in a single update.
			frappe.db.set_value(
				"DocType Settings Map",
				{"applies_to_doctype": self.applies_to_doctype, "name": ("!=", self.name)},
				"is_active",
				0,
			)
			return

		# Dev-lock fallback (beyond the vanilla pattern): if deactivating leaves nothing active,
		# re-activate the standard sibling (else any) — the standard can't be re-enabled by users
		# directly, so we keep one map active rather than stranding the doctype with none.
		siblings = frappe.get_all(
			"DocType Settings Map",
			filters={"applies_to_doctype": self.applies_to_doctype, "name": ("!=", self.name)},
			fields=["name", "is_standard", "is_active"],
		)
		if siblings and not any(s.is_active for s in siblings):
			fallback = next((s for s in siblings if s.is_standard), siblings[0])
			frappe.db.set_value("DocType Settings Map", fallback.name, "is_active", 1)

	def _set_sibling_active(self):
		"""On deletion of the active map, activate a remaining sibling (prefer standard)."""
		siblings = frappe.get_all(
			"DocType Settings Map",
			filters={"applies_to_doctype": self.applies_to_doctype, "name": ("!=", self.name)},
			fields=["name"],
			order_by="is_standard desc",
			limit=1,
		)
		if siblings:
			frappe.db.set_value("DocType Settings Map", siblings[0].name, "is_active", 1)
