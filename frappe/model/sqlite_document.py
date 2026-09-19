# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""Document behaviour for DocTypes with `use_sqlite` enabled.

The mixin implements the same surface as `frappe.model.virtual_doctype.VirtualDoctype` --
that protocol is the right seam between the document lifecycle and a non-default store --
but every method delegates straight back to the standard implementation with the SQLite
side store swapped in. Nothing about persistence, querying or permissions is reimplemented.

These DocTypes keep `is_virtual = 0` on purpose. `is_virtual` means "the framework owns no
table for this DocType", which would take away schema sync (`DBTable.sync`), the delete
pipeline (`frappe.model.delete_doc`), link integrity and the `frappe.db.*` helpers -- all of
which work fine here, because a real table does exist, just in a different file.
"""

import frappe
from frappe.database.sqlite.router import use_sqlite_db
from frappe.model.document import Document


class SQLiteDocumentMixin:
	"""Route a Document's own table I/O to the SQLite side store."""

	# ============ instance methods ============

	def db_insert(self, *args, **kwargs):
		with use_sqlite_db():
			return super().db_insert(*args, **kwargs)

	def db_update(self, *args, **kwargs):
		with use_sqlite_db():
			return super().db_update(*args, **kwargs)

	def db_update_all(self, *args, **kwargs):
		with use_sqlite_db():
			return super().db_update_all(*args, **kwargs)

	def load_from_db(self, *args, **kwargs):
		with use_sqlite_db():
			return super().load_from_db(*args, **kwargs)

	# `delete` is deliberately not overridden. `Document.delete` hands off to
	# `frappe.model.delete_doc`, whose pipeline -- link integrity, Deleted Document,
	# versions, comments -- belongs to the primary database. Only the row delete itself
	# targets the side store, and `delete_doc.delete_from_table` routes that directly.

	# ============ class/static methods ============

	@staticmethod
	def get_list(**kwargs):
		from frappe.model.db_query import DatabaseQuery

		doctype = kwargs.pop("doctype")
		with use_sqlite_db():
			return DatabaseQuery(doctype).execute(**kwargs)

	@staticmethod
	def get_count(**kwargs):
		from frappe.model.db_query import DatabaseQuery

		doctype = kwargs.pop("doctype")
		with use_sqlite_db():
			return DatabaseQuery(doctype).execute(**kwargs)

	@staticmethod
	def get_stats(**kwargs):
		from frappe.desk.reportview import get_stats

		with use_sqlite_db():
			return get_stats(**kwargs)


class SQLiteDocument(SQLiteDocumentMixin, Document):
	"""Controller used for SQLite-backed DocTypes that ship no controller file of their own."""


def get_sqlite_controller(base_class):
	"""Return `base_class` with SQLite routing mixed in, preserving its own behaviour.

	Mirrors `frappe.model.base_document._get_extended_class`: a new type is synthesised
	rather than mutating the controller, so a DocType that does ship a controller keeps its
	validate/on_update hooks while its table I/O is redirected.
	"""
	if issubclass(base_class, SQLiteDocumentMixin):
		return base_class

	return type(base_class.__name__, (SQLiteDocumentMixin, base_class), {})
