# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import strip_default_fields


class Widget(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.desk.doctype.widget_link_value.widget_link_value import WidgetLinkValue
		from frappe.types import DF

		config: DF.JSON | None
		hide_filter: DF.Check
		label: DF.Data
		links: DF.Table[WidgetLinkValue]
		module: DF.Link | None
		type: DF.Link
	# end: auto-generated types

	def autoname(self):
		self.name = new_widget_name(self.label, self.type, self.module)

	def before_validate(self):
		links = {row.fieldname: row.link_name for row in self.links}
		self.split_config(links | frappe.parse_json(self.config or "{}"))
		# Frappe checked links before this filled them
		self._validate_links()

	def validate(self):
		from frappe.desk.widgets import get_type_class

		widget_class = get_type_class(self.type)
		if not widget_class:
			frappe.throw(_("Widget Type {0} does not exist.").format(frappe.bold(self.type)))
		widget_class(self).validate()

	def on_update(self):
		if self.is_exported():
			self.export()

	def on_trash(self):
		if self.is_exported() and os.path.exists(path := self.file_path()):
			os.remove(path)

	def get_config(self) -> dict:
		"""The widget's props, its links included, as its type and renderer see them."""
		config = frappe.parse_json(self.config or "{}")
		config.update({row.fieldname: row.link_name for row in self.links})
		return config

	def split_config(self, config: dict):
		"""Keep Link props in `links`, where a rename or delete of the record follows them."""
		links = []
		values = dict(config)
		for field in self.get_fields():
			value = config.get(field.fieldname)
			if field.fieldtype in ("Link", "Dynamic Link"):
				config.pop(field.fieldname, None)
				link_doctype = (
					values.get(field.options) if field.fieldtype == "Dynamic Link" else field.options
				)
				if value and link_doctype:
					links.append(
						{"fieldname": field.fieldname, "link_doctype": link_doctype, "link_name": value}
					)
			elif field.fieldtype == "JSON" and field.options and value:
				config[field.fieldname] = short_filters(frappe.parse_json(value), values.get(field.options))
		self.config = frappe.as_json(config, indent=None)
		self.set("links", links)

	def get_fields(self) -> list:
		from frappe.desk.widgets import get_types

		fields = (get_types().get(self.type) or {}).get("fields") or []
		return [frappe._dict(field) for field in fields]

	def is_exported(self) -> bool:
		return bool(
			frappe.conf.developer_mode
			and self.module
			and not frappe.flags.in_import
			and not frappe.db.get_value("Module Def", self.module, "custom")
		)

	def file_path(self) -> str:
		return os.path.join(
			get_module_path(self.module), "widgets", scrub(self.type), f"{scrub(self.name)}.json"
		)

	def export(self):
		path = self.file_path()
		frappe.create_folder(os.path.dirname(path))
		with open(path, "w") as f:  # nosemgrep
			f.write(frappe.as_json(strip_default_fields(self, self.as_dict(no_nulls=True))) + "\n")


def new_widget_name(label: str, widget_type: str, module: str | None) -> str:
	"""`<module>-<label>` for an app's widget, `(<Type>)` added once when another type took it.

	A site's widget takes the bare label, numbered when taken.
	"""
	if not module:
		return append_number_if_name_exists("Widget", label)
	name = f"{module}-{label}"
	if frappe.db.exists("Widget", name):
		name = f"{name} ({widget_type})"
	return append_number_if_name_exists("Widget", name)


def short_filters(filters: list | dict, doctype: str | None) -> list:
	"""Filter rows as `[field, op, value]`. A row on a child table keeps its doctype."""
	if isinstance(filters, dict):
		filters = [
			[field, *(value if isinstance(value, list) else ["=", value])] for field, value in filters.items()
		]
	return [row[1:] if row[0] == doctype else row for row in filters]
