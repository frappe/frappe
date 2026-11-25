# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.utils import cstr

CODE_AUTHOR_ROLE = "Code Author"
# Script Managers already write Server Scripts, which run the same sandbox
CODE_AUTHOR_ROLES = (CODE_AUTHOR_ROLE, "Script Manager")


class CodeFieldGuard:
	"""Only a Code Author can change fields marked `executes_code` (Jinja or Python run on the server)."""

	def __init__(self, doc, fields=None, tables=None):
		"""`fields`, `tables` ([(table_df, child_fields)]): check these instead of the ones marked `executes_code`."""
		self.doc = doc
		self.fields, self.tables = fields, tables

	def validate(self):
		# a restore re-inserts the snapshot saved when the document was deleted
		if self.doc.flags.ignore_permissions or self.doc.flags.from_restore or frappe.flags.in_install:
			return

		# only after the skips: during install, child DocTypes may not be synced yet
		self.load_fields()
		if not (self.fields or self.tables) or is_code_author():
			return

		if changed := self.get_changed_labels():
			frappe.throw(
				_("Only a user with the {0} role can change: {1}").format(
					_(CODE_AUTHOR_ROLE), ", ".join(changed)
				),
				frappe.PermissionError,
				title=_("Not Permitted"),
			)

	def load_fields(self):
		if self.fields is not None or self.tables is not None:
			self.fields, self.tables = self.fields or [], self.tables or []
			return

		self.fields = self.doc.meta.get_executable_fields()
		self.tables = [
			(df, child_fields)
			for df in self.doc.meta.get_table_fields()
			if (child_fields := frappe.get_meta(df.options).get_executable_fields())
		]

	def get_changed_labels(self):
		doc = self.doc
		saved = None if doc.is_new() else doc.get_latest()
		reference = saved or frappe.new_doc(doc.doctype, as_dict=True)
		changed = [
			_(df.label) for df in self.fields if self.is_authored(doc, reference, df, is_new=not saved)
		]

		for table_df, child_fields in self.tables:
			changed.extend(self.get_changed_row_labels(table_df, child_fields, saved))

		return changed

	def get_changed_row_labels(self, table_df, child_fields, saved):
		# compare only with this parent's own saved rows: a row name taken from
		# another parent is treated as a new row
		saved_rows = {row.name: row for row in saved.get(table_df.fieldname)} if saved else {}
		defaults = None
		changed = []

		for row in self.doc.get(table_df.fieldname):
			reference = saved_rows.get(row.name)
			is_new = reference is None
			if is_new:
				defaults = defaults or frappe.new_doc(
					table_df.options, parent_doc=self.doc, parentfield=table_df.fieldname, as_dict=True
				)
				reference = defaults

			changed.extend(
				_("{0} (row {1})").format(_(df.label), row.idx)
				for df in child_fields
				if self.is_authored(row, reference, df, is_new, child_doctype=table_df.options)
			)

		return changed

	def is_authored(self, row, reference, df, is_new, child_doctype=None):
		# clearing a field runs nothing
		if not is_changed(row, reference, df) or not normalize(row.get(df.fieldname), df):
			return False
		# a new document or row may reuse code the user can already read, e.g. after Duplicate
		return not (
			is_new and self.exists_in_readable_doc(df.fieldname, row.get(df.fieldname), child_doctype)
		)

	def exists_in_readable_doc(self, fieldname, value, child_doctype=None):
		source = child_doctype or self.doc.doctype
		filters = [[source, fieldname, "=", value], *self.get_source_filters(fieldname, value, child_doctype)]
		# SQL equality ignores case and trailing spaces under MariaDB collations, Python does not;
		# distinct keeps one row per collation match instead of every document that holds it
		rows = frappe.get_list(
			self.doc.doctype,
			filters=filters,
			fields=[f"`tab{source}`.`{fieldname}`"],
			distinct=True,
			as_list=True,
		)
		return any(row[0] == value for row in rows)

	def get_source_filters(self, fieldname, value, child_doctype=None):
		"""Extra filters for the copied value's source, e.g. that it also runs the value as code."""
		return []


def is_code_author(user=None):
	return not set(CODE_AUTHOR_ROLES).isdisjoint(frappe.get_roles(user))


def is_changed(doc, reference, df):
	return normalize(doc.get(df.fieldname), df) != normalize(reference.get(df.fieldname), df)


def normalize(value, df):
	if df.fieldtype == "JSON" and value not in (None, ""):
		# APIs may send a JSON field parsed, the database holds it as text
		return frappe.parse_json(value)
	# code editors and APIs differ in line endings, trailing whitespace and None vs ""
	return cstr(value).replace("\r\n", "\n").strip()
