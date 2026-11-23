# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE
import frappe
from frappe import _
from frappe.utils import cstr

CODE_AUTHOR_ROLE = "Code Author"


class CodeFieldGuard:
	"""Only a Code Author can change fields marked `executes_code` (Jinja or Python run on the server)."""

	def __init__(self, doc):
		self.doc = doc
		self.fields = doc.meta.get_executable_fields()
		self.tables = [
			(df, child_fields)
			for df in doc.meta.get_table_fields()
			if (child_fields := frappe.get_meta(df.options).get_executable_fields())
		]

	def validate(self):
		if self.doc.flags.ignore_permissions or frappe.flags.in_install:
			return

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

	def get_changed_labels(self):
		doc = self.doc
		saved = None if doc.is_new() else doc.get_latest()
		reference = saved or frappe.new_doc(doc.doctype, as_dict=True)
		changed = [_(df.label) for df in self.fields if is_changed(doc, reference, df.fieldname)]

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
			if reference is None:
				defaults = defaults or frappe.new_doc(
					table_df.options, parent_doc=self.doc, parentfield=table_df.fieldname, as_dict=True
				)
				reference = defaults

			changed.extend(
				_("{0} (row {1})").format(_(df.label), row.idx)
				for df in child_fields
				if is_changed(row, reference, df.fieldname)
			)

		return changed


def is_code_author(user=None):
	return CODE_AUTHOR_ROLE in frappe.get_roles(user)


def is_changed(doc, reference, fieldname):
	return normalize(doc.get(fieldname)) != normalize(reference.get(fieldname))


def normalize(value):
	# code editors and APIs differ in line endings, trailing whitespace and None vs ""
	return cstr(value).replace("\r\n", "\n").strip()
