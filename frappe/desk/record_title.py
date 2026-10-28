# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

"""A record's title as the desk draws it, whatever "show title in link fields" says."""

from html import unescape

import frappe
from frappe import _
from frappe.model import get_permitted_fields
from frappe.utils import cstr, strip_html


class RecordTitles:
	"""A doctype's record titles: the title field's value as plain text, else the name; translated where the doctype is."""

	def __init__(self, doctype: str):
		self.meta = frappe.get_meta(doctype)
		self.field = readable_title_field(self.meta)

	@property
	def columns(self) -> list[str]:
		"""The columns a query reads so that `of` needs no second query."""
		return [self.field.fieldname] if self.field and not self.field.is_virtual else []

	def of(self, rows: list[dict]) -> dict[str, str]:
		"""`{name: title}` for `rows`, which the caller has checked the user may read."""
		values = self.values(rows) if self.field else {}
		return {row["name"]: self.title(values.get(row["name"]), row["name"]) for row in rows}

	def values(self, rows: list[dict]) -> dict:
		if self.field.is_virtual:
			return {
				row["name"]: frappe.get_doc(self.meta.name, row["name"]).get_virtual_field_value(self.field)
				for row in rows
			}

		fieldname = self.field.fieldname
		values = {row["name"]: row[fieldname] for row in rows if fieldname in row}
		# a hooked search query may return rows without the title column
		if missing := [row["name"] for row in rows if fieldname not in row]:
			values.update(
				frappe.get_all(
					self.meta.name,
					filters={"name": ("in", missing)},
					fields=["name", fieldname],
					as_list=True,
				)
			)
		return values

	def title(self, value, name: str) -> str:
		title = plain_text(value) or cstr(name)
		return _(title) if self.meta.translated_doctype else title


def readable_title_field(meta):
	"""The doctype's title field, or None where it has none or the user may not read it."""
	field = meta.get_field(meta.title_field) if meta.title_field else None
	if field and field.fieldname in get_permitted_fields(meta.name):
		return field
	return None


def plain_text(value) -> str:
	# a Text Editor holds HTML, and saving sanitises a Data value holding tags, escaping its "&"
	return unescape(strip_html(cstr(value))).strip()
