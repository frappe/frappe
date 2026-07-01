# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

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

	def autoname(self):
		# Name the record after the doctype it applies to. A doctype may have both a custom
		# and a standard map, which can't share a name — the custom (user-created) one keeps
		# the plain doctype name; the standard one is suffixed to stay unique.
		self.name = self.applies_to_doctype
		if self.is_standard:
			self.name = f"{self.applies_to_doctype} (Standard)"

	def validate(self):
		self._guard_standard()
		self._validate_unique_per_doctype()
		# Standard maps ship with an app; default the owning module to the one that owns the
		# doctype they apply to (the dev can override). Custom maps aren't exported.
		if self.is_standard and not self.module:
			self.module = frappe.db.get_value("DocType", self.applies_to_doctype, "module")

	def on_update(self):
		self._enforce_single_active()
		self.export_doc()

	def export_doc(self):
		"""Write standard maps to the app's module folder as JSON (developer mode only), so
		they ship in code and sync to other sites on migrate — like standard Print Formats.
		Custom maps (is_standard=0) are a no-op and stay in the site DB."""
		from frappe.modules.utils import export_module_json

		return export_module_json(self, self.is_standard, self.module, create_init=False)

	def on_trash(self):
		self._guard_standard()
		# If the active map is being deleted, promote the remaining one (prefer standard).
		if self.is_active:
			self._set_sibling_active()

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
		"""At most one standard and one custom map per doctype."""
		if frappe.db.exists(
			"DocType Settings Map",
			{
				"applies_to_doctype": self.applies_to_doctype,
				"is_standard": self.is_standard,
				"name": ("!=", self.name),
			},
		):
			kind = _("standard") if self.is_standard else _("custom")
			frappe.throw(
				_("A {0} settings map already exists for {1}.").format(kind, self.applies_to_doctype)
			)

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
