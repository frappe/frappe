# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Custom Import Providers for Data Import.

Data Import owns the whole workflow (dialog, upload, parse, mapping, preview, basic
type/Link/date validation, background job, progress, logs, status). A *provider* supplies
only the parts Data Import cannot know for a complex/custom import — three methods:

1. ``get_import_fields`` — the field schema in the format the field-picker dialog needs:
   parent ``fields`` + ``child_tables``, each a **complete docfield (DF)**. The provider is
   free to build these however it likes — from ``frappe.get_meta`` (like Customer), or
   hand-authored for columns that don't belong to any DocType.
2. ``validate`` — business validation on top of the framework's basic checks.
3. ``import_row`` — create the actual documents for one parsed record.

Register in any app's ``hooks.py``::

    data_import_providers = {
        "Customer": "erpnext.selling.doctype.customer.customer_import_provider.CustomerImportProvider"
    }
"""

import frappe


class ImportProvider:
	"""Base class for a Data Import provider. Subclass and register via hooks."""

	#: The reference DocType this provider handles. Set by ``get_import_provider``.
	doctype: str | None = None

	def get_import_fields(self) -> dict | None:
		"""The field schema for the picker dialog (and, later, mapping + type-checks).

		Shape — same as a DocType with child tables, values are **complete docfields**::

		    {"fields": [<df>, ...],
		     "child_tables": [{"fieldname", "label", "fields": [<df>, ...]}, ...]}

		Each ``<df>`` is a docfield dict (``fieldname, label, fieldtype, options, reqd, ...``).
		Return ``None`` for a plain single-DocType import (framework uses meta as usual).
		"""
		return None

	def validate(self, import_file) -> list[dict]:
		"""Business validation over the parsed file. Return warning dicts
		``{"row": int, "message": str, "type"?: "info"}``. Non-``info`` warnings block import.
		Basic Select/Link/Date checks are already done by Data Import. Default: none."""
		return []

	def import_row(self, importer, doc):
		"""Create the documents for one parsed record. ``doc`` is the parsed parent dict with
		child rows under each child table's fieldname. Return ``(document, import_action)``."""
		raise NotImplementedError


def get_import_provider(doctype: str) -> ImportProvider | None:
	"""Resolve the registered provider for ``doctype``, or ``None``."""
	if not doctype:
		return None
	# When no app registers `data_import_providers`, get_hooks returns an empty list
	# (not a dict), so guard the type before .get().
	hooks = frappe.get_hooks("data_import_providers")
	if not isinstance(hooks, dict):
		return None
	paths = hooks.get(doctype)
	if not paths:
		return None
	provider = frappe.get_attr(paths[-1] if isinstance(paths, list | tuple) else paths)()
	provider.doctype = doctype
	return provider
