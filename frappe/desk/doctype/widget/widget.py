# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import os

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.model.naming import append_number_if_name_exists
from frappe.modules import get_module_path, scrub
from frappe.modules.export_file import exports_to_app, write_record
from frappe.utils.data import cast


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
		# an app's widget comes from its files, or from a developer saving one there
		if self.module and not (
			frappe.conf.developer_mode or frappe.flags.in_import or frappe.flags.in_install
		):
			self.module = None
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
		clear_pages_cache()
		if self.is_exported():
			self.export()

	def on_trash(self):
		clear_pages_cache()
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
			if config.get(field.fieldname) is None and field.default is not None:
				config[field.fieldname] = cast(field.fieldtype, field.default)
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
		return exports_to_app(self.module)

	def file_path(self) -> str:
		return os.path.join(
			get_module_path(self.module), "widgets", scrub(self.type), f"{scrub(self.name)}.json"
		)

	def export(self):
		write_record(self, self.file_path())


def clear_pages_cache():
	"""A merged page holds the items of the cards a layout reaches into."""
	from frappe.desk.layouts import PAGES_KEY

	frappe.cache.delete_keys(f"{PAGES_KEY}|")


def new_widget_name(label: str, widget_type: str, module: str | None) -> str:
	"""`<module>-<label>` for an app's widget, `(<Type>)` added once when a widget of another type
	took it, and numbered when one of its own type did.

	A site's widget takes the bare label, numbered when taken.
	"""
	if not module:
		return append_number_if_name_exists("Widget", label)
	name = f"{module}-{label}"
	taken_by = frappe.db.get_value("Widget", name, "type")
	if taken_by and taken_by != widget_type:
		name = f"{name} ({widget_type})"
	return append_number_if_name_exists("Widget", name)


def short_filters(filters: list | dict, doctype: str | None) -> list | dict:
	"""Filter rows as `[field, op, value]`. A row on a child table keeps its doctype, and a report's
	filters, a dict, stay as they are."""
	if isinstance(filters, dict):
		return filters
	return [row[1:] if row[0] == doctype else row for row in filters]
