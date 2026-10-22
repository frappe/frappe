# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""An import provider is an app class that takes over validation and record creation for one
DocType's import. Register it in hooks.py: ``data_import_providers = {doctype: "dotted.path.Class"}``."""

import frappe


class ImportProvider:
	"""Subclass this and register it under ``data_import_providers``."""

	#: The DocType being imported; set by ``get_import_provider``.
	doctype: str | None = None

	def get_import_fields(self) -> dict | None:
		"""Fields for the picker and column matching, or None to use the DocType's meta.

		Shape: ``{"fields": [df, ...], "child_tables": [{"fieldname", "label", "fields": [df, ...]}]}``
		where each ``df`` is a complete docfield dict.
		"""
		return None

	def validate(self, import_file) -> list[dict]:
		"""Return warnings ``{"row": int, "message": str, "type"?: "info"}`` for the parsed file.
		Any warning whose type is not "info" blocks the import. Link/Select/date checks already ran."""
		return []

	def import_row(self, importer, doc):
		"""Create the documents for one record and return ``(document, import_action)``.
		``doc`` is the parent dict with child rows under each table's fieldname."""
		raise NotImplementedError

	def get_export_rows(self, names: list[str], tables: dict[str, list[str]]) -> dict[str, dict[str, list]]:
		"""Rows of the extra ``child_tables`` for the records being exported, or {} to leave them blank.

		``tables`` maps each exported extra table to its exported fieldnames. Return
		``{record_name: {table_fieldname: [row_dict, ...]}}``. The exporter does not check
		permissions on these rows, so fetch them with ``frappe.get_list``."""
		return {}


def get_import_provider(doctype: str) -> ImportProvider | None:
	"""Resolve the registered provider for ``doctype``, or ``None``."""
	if not doctype:
		return None
	# get_hooks returns [] rather than {} when nothing is registered.
	hooks = frappe.get_hooks("data_import_providers")
	if not isinstance(hooks, dict):
		return None
	paths = hooks.get(doctype)
	if not paths:
		return None
	provider = frappe.get_attr(paths[-1] if isinstance(paths, list | tuple) else paths)()
	provider.doctype = doctype
	return provider
