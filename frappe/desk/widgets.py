# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""Widgets: one thing drawn on a workspace, of a Widget Type that says what it holds and how it draws.

A type's Python class lives beside its record, found the way a DocType's controller is:

    <app>/<module>/widget_type/<type>/<type>.py  ->  class <Type>(WidgetType)

The server works out each widget's data while it builds the page. A widget that is missing, whose
type is missing, that the user may not read, or whose `get_data` returns None is left off the page.
"""

import hashlib
import importlib
import json

import frappe
from frappe import _
from frappe.desk.utils import is_item_allowed
from frappe.utils.caching import request_cache

TYPES_CACHE_KEY = "widget_types"
# the most widgets one refresh call works out
MAX_REFRESH = 50
LINK_FIELDTYPES = ("Link", "Dynamic Link")


class WidgetType:
	"""The base of every widget type's class. A type overrides what it needs."""

	# seconds a widget's data stays cached per user; 0 turns the cache off
	cache_ttl = 300

	def __init__(self, widget):
		self.doc = widget
		self.name = widget.name
		self.config = widget.get_config()

	def get_data(self, filters: dict | None = None):
		"""What the renderer draws. None leaves the widget off the page."""
		return {}

	def has_permission(self, user: str | None = None) -> bool:
		"""Whether `user` may see this widget: by default, they can read every record it links to."""
		return all(can_read(row.link_doctype, row.link_name, user) for row in self.doc.links)

	def validate(self):
		"""Called when the widget is saved, after its config is split into links."""

	def filters(self, reader_filters: dict | None = None, key: str = "filters") -> list:
		"""The filters prop `key`, replaced by the reader's own when they set one."""
		filters = frappe.parse_json((reader_filters or {}).get(key) or self.config.get(key) or [])
		rows = (
			[[field, "=", value] for field, value in filters.items()]
			if isinstance(filters, dict)
			else filters
		)
		return [[frappe.session.user if value == "@me" else value for value in row] for row in rows]

	def count(self, doctype: str, filters: list | None = None) -> int:
		return self.aggregate(doctype, "COUNT", "*", filters)

	def aggregate(self, doctype: str, function: str, field: str, filters: list | None = None):
		rows = frappe.get_list(doctype, fields=[{function: field, "as": "result"}], filters=filters or [])
		return rows[0]["result"] if rows else 0

	def cached_data(self, filters: dict | None = None):
		if not self.cache_ttl or self.doc.flags.no_cache:
			return self.get_data(filters)
		key = self.cache_key(filters)
		hit = frappe.cache.get_value(key, user=frappe.session.user)
		if hit is not None:
			return hit["data"]
		data = self.get_data(filters)
		frappe.cache.set_value(key, {"data": data}, user=frappe.session.user, expires_in_sec=self.cache_ttl)
		return data

	def clear_cached_data(self, filters: dict | None = None):
		frappe.cache.delete_value(self.cache_key(filters), user=frappe.session.user)

	def cache_key(self, filters: dict | None) -> str:
		digest = hashlib.md5(json.dumps(filters or {}, sort_keys=True).encode()).hexdigest()
		return f"widget_data|{self.name}|{self.doc.modified}|{digest}"


def get_types() -> dict:
	"""Every Widget Type on the site: its island, sizes and props."""
	return frappe.client_cache.get_value(TYPES_CACHE_KEY, generator=build_types)


def clear_types_cache():
	frappe.client_cache.delete_value(TYPES_CACHE_KEY)


def build_types() -> dict:
	types = {}
	for doc in frappe.get_all("Widget Type", pluck="name"):
		widget_type = frappe.get_doc("Widget Type", doc)
		types[widget_type.name] = {
			"module": widget_type.module,
			"island": widget_type.island or island_name(widget_type),
			"child_type": widget_type.child_type,
			"sizes": {row.size: [row.cols, row.rows or None] for row in widget_type.sizes},
			"fields": [field_spec(row) for row in widget_type.fields],
		}
	return types


def field_spec(row) -> dict:
	return {
		"fieldname": row.fieldname,
		"label": row.label,
		"fieldtype": row.fieldtype,
		"options": row.options,
		"reqd": row.reqd,
		"default": row.default,
		"in_standard_filter": row.in_standard_filter,
	}


def island_name(widget_type) -> str:
	return f"{app_of(widget_type.module)}.widget.{frappe.scrub(widget_type.name)}"


def app_of(module: str | None) -> str | None:
	"""The app that ships `module`, or None for a site's own module or one whose app is gone."""
	return frappe.local.module_app.get(frappe.scrub(module)) if module else None


def get(name: str) -> WidgetType | None:
	"""The widget `name` with its type's class, or None when it or its type is missing."""
	try:
		widget = frappe.get_cached_doc("Widget", name)
	except frappe.DoesNotExistError:
		frappe.clear_last_message()
		return None
	widget_class = get_type_class(widget.type)
	return widget_class(widget) if widget_class else None


def get_type_class(type_name: str) -> type[WidgetType] | None:
	spec = get_types().get(type_name)
	if not spec:
		return None
	return load_type_class(spec["module"], type_name)


@request_cache
def load_type_class(module: str, type_name: str) -> type[WidgetType]:
	app = app_of(module)
	if not app:
		return WidgetType
	scrubbed = frappe.scrub(type_name)
	path = f"{app}.{frappe.scrub(module)}.widget_type.{scrubbed}.{scrubbed}"
	try:
		module = importlib.import_module(path)
	except ModuleNotFoundError as e:
		if not path.startswith(e.name or ""):
			raise
		return WidgetType
	return getattr(module, type_name.replace(" ", "").replace("-", ""))


def build_widgets(content: list) -> dict:
	"""Each widget block's payload by block id, leaving out the ones the session user does not get.

	A container's block may carry its own `items`, which layouts changed, in place of its widget's.
	"""
	widgets = {}
	for block in content:
		if block.get("type") != "widget" or not (widget := get(block["data"]["widget"])):
			continue
		if "items" in block["data"]:
			widget.config["widgets"] = [{"widget": item["widget"]} for item in block["data"]["items"]]
		if (built := payload(widget, None)) is not None:
			widgets[block["id"]] = built
	return widgets


def build_widget(name: str, filters: dict | None = None) -> dict | None:
	widget = get(name)
	return payload(widget, filters) if widget else None


@frappe.whitelist(methods=["POST"])
def refresh(names: list[str], filters: dict | None = None) -> dict:
	"""Fresh data for the named widgets, each with the reader's own filters: `{name: {prop: value}}`."""
	filters = frappe.parse_json(filters) or {}
	refreshed = {}
	for name in frappe.parse_json(names)[:MAX_REFRESH]:
		widget = get(name)
		if not widget:
			continue
		reader = reader_filters(widget, filters.get(name))
		widget.clear_cached_data(reader)
		if (fresh := payload(widget, reader)) is not None:
			refreshed[name] = fresh
	return refreshed


@frappe.whitelist(methods=["POST"])
def preview(type: str, config: dict, label: str = "") -> dict | None:
	"""A draft widget the editor has not saved yet, drawn as it would be."""
	frappe.has_permission("Widget", "write", throw=True)
	return build_unsaved_widget("preview", type, label, frappe.parse_json(config), cache=False)


def reader_filters(widget: WidgetType, values: dict | None) -> dict | None:
	"""The reader's own values for the props a reader may change, refused for any other prop."""
	if not values:
		return None
	if widget.doc.hide_filter:
		frappe.throw(_("This widget's filters cannot be changed."), frappe.PermissionError)
	fields = {field.fieldname: field for field in widget.doc.get_fields() if field.in_standard_filter}
	for fieldname, value in values.items():
		field = fields.get(fieldname)
		if not field:
			frappe.throw(_("{0} cannot be changed by a reader.").format(fieldname), frappe.PermissionError)
		if field.fieldtype == "Select" and value not in (field.options or "").split("\n"):
			frappe.throw(_("{0} is not an option for {1}.").format(value, _(field.label)))
	return values


def build_unsaved_widget(
	name: str, widget_type: str, label: str, config: dict, cache: bool = True
) -> dict | None:
	"""The payload of a widget the page generates, which has no record. A draft's config changes
	with each preview, so it is never cached."""
	doc = frappe.new_doc("Widget", type=widget_type, label=label, config=frappe.as_json(config))
	doc.name = name
	doc.flags.no_cache = not cache
	widget_class = get_type_class(widget_type)
	return payload(widget_class(doc), None) if widget_class else None


def payload(widget: WidgetType, filters: dict | None) -> dict | None:
	"""What the browser gets for one widget, or None when this user does not get it."""
	if not widget.has_permission():
		return None
	try:
		data = widget.cached_data(filters)
	except Exception:
		# one widget that fails leaves the page, never takes it down
		frappe.log_error(_("Widget {0} failed to load").format(widget.name))
		return None
	if data is None:
		return None
	return {
		"name": widget.name,
		"label": _(widget.doc.label),
		"type": widget.doc.type,
		"config": widget.config,
		"hide_filter": widget.doc.hide_filter,
		"data": data,
	}


@request_cache
def can_read(doctype: str, name: str, user: str | None = None) -> bool:
	if doctype in ("DocType", "Report", "Page", "Dashboard", "Workspace"):
		return is_item_allowed(name, doctype, desk_views())
	return frappe.has_permission(doctype, "read", name, user=user)


@request_cache
def desk_views():
	from frappe.desk.desk_views import DeskViews

	return DeskViews()
