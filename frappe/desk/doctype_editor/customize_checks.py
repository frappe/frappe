# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE
"""What a Customize save checks before its first write: Customize Form's refusals, keyed to the field."""

from functools import cached_property

import frappe
from frappe import _
from frappe.core.doctype.doctype.doctype import validate_fields
from frappe.custom.doctype.customize_form.customize_form import (
	docfield_properties,
	is_standard_or_system_generated_field,
)
from frappe.desk.doctype_editor.checks import DesignChecks
from frappe.desk.doctype_editor.customize_state import CustomizeState
from frappe.desk.doctype_editor.errors import field_error
from frappe.model.meta import Meta


class CustomizeChecks(DesignChecks):
	state: CustomizeState

	def __init__(self, state: CustomizeState):
		super().__init__(state)
		self.skipped: list[dict] = []

	def parent_errors(self) -> list[dict]:
		"""A refusal that does not block skips its change: Customize Form leaves that property alone."""
		errors = self.rename_errors() + self.refusal_errors()
		if not errors:
			validate_fields(self.meta)
		return errors

	def rename_errors(self) -> list[dict]:
		if not self.state.renames or "System Manager" in frappe.get_roles():
			return []
		message = _("Renaming a custom field needs the System Manager role.")
		return [field_error(message, new).as_dict() for _old, new in self.state.renames]

	def refusal_errors(self) -> list[dict]:
		form, meta = self.state.doc, frappe.get_meta(self.state.name)
		errors = []
		for df in form.fields:
			meta_df = meta.get("fields", {"fieldname": df.fieldname})
			for prop in docfield_properties if meta_df else ():
				if prop == "idx" or (df.get(prop) or "") == (meta_df[0].get(prop) or ""):
					continue
				if refusal := self.refusal(prop, meta_df, df, meta):
					error = field_error(refusal.message, df.fieldname, prop).as_dict()
					(errors if refusal.blocks_save else self.skipped).append(error)
		return errors

	def refusal(self, prop: str, meta_df: list, df, meta):
		form = self.state.doc
		if is_standard_or_system_generated_field(meta_df[0]):
			return form.check_property_change(prop, meta_df, df, meta)
		if prop == "fieldtype":
			return form.check_fieldtype_change(df, meta_df[0].fieldtype, df.fieldtype)

	@cached_property
	def meta(self) -> Meta:
		"""The DocType's meta with the fields as this save leaves them."""
		meta = Meta(self.state.name)
		meta.fields = [as_docfield(field) for field in self.state.doc.fields]
		meta.init_field_caches()
		return meta


def as_docfield(field):
	"""DocType's field checks read DocField properties that Customize Form Field lacks."""
	return frappe.new_doc("DocField").update(field.as_dict(no_default_fields=True))
