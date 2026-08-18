# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import json
import re

import frappe
from frappe import _
from frappe.model.document import Document

FORM_LAYOUT_TYPES = ("Details", "Side Panel", "Quick Entry")


class FormLayout(Document):
	def validate(self):
		self.validate_single_default()

	def validate_single_default(self):
		if self.condition:
			return
		default = frappe.get_all(
			"Form Layout",
			filters={
				"dt": self.dt,
				"type": self.type,
				"condition": ("is", "not set"),
				"name": ("!=", self.name or ""),
			},
			limit=1,
		)
		if default:
			frappe.throw(
				_("A default Form Layout already exists for {0} ({1}). Add a condition to this one.").format(
					self.dt, self.type
				)
			)


@frappe.whitelist()
def get_form_layouts(dt: str, type: str):
	if type not in FORM_LAYOUT_TYPES:
		frappe.throw(_("Invalid Form Layout type: {0}").format(type))
	frappe.has_permission(dt, "read", throw=True)

	rows = frappe.get_all(
		"Form Layout",
		filters={"dt": dt, "type": type},
		fields=["name", "condition", "layout"],
		order_by="creation asc",
	)
	layouts = [
		{"name": row.name, "condition": row.condition, "layout": parse_layout(row.layout)} for row in rows
	]
	return {"layouts": layouts, "fallback": get_meta_layout(dt)}


@frappe.whitelist()
def save_form_layout(
	dt: str, type: str, layout: str, name: str | None = None, condition: str | None = None
):
	frappe.has_permission("Form Layout", "write", throw=True)
	doc = find_layout_doc(dt, type, name)
	doc.update({"dt": dt, "type": type, "layout": layout, "condition": condition})
	doc.save()
	return doc.name


def find_layout_doc(dt: str, type: str, name: str | None):
	if name:
		return frappe.get_doc("Form Layout", name)
	default = frappe.get_all(
		"Form Layout", filters={"dt": dt, "type": type, "condition": ("is", "not set")}, limit=1
	)
	if default:
		return frappe.get_doc("Form Layout", default[0].name)
	return frappe.new_doc("Form Layout")


def parse_layout(layout: str | None) -> list:
	tree = json.loads(layout) if layout else []
	if not isinstance(tree, list):
		return []
	tabs = wrap_tabless(tree)
	name_layout_containers(tabs)
	return tabs


def wrap_tabless(tree: list) -> list:
	nodes = [node for node in tree if isinstance(node, dict)]
	if any("sections" in node for node in nodes):
		return nodes
	return [{"name": "first_tab", "sections": nodes}]


def name_layout_containers(tabs: list):
	assign_names(tabs, "tab")
	for tab in tabs:
		tab["sections"] = [section for section in tab.get("sections") or [] if isinstance(section, dict)]
		assign_names(tab["sections"], "section")
		for section in tab["sections"]:
			section["columns"] = [column for column in section.get("columns") or [] if isinstance(column, dict)]
			assign_names(section["columns"], "column")
			for column in section["columns"]:
				column["fields"] = [field for field in column.get("fields") or [] if field]


def assign_names(nodes: list, kind: str):
	taken = {node.get("name") for node in nodes if node.get("name")}
	for index, node in enumerate(nodes, start=1):
		if node.get("name"):
			continue
		name = slugify(node.get("label")) or f"{kind}_{index}"
		if name in taken:
			name = f"{name}_{index}"
		node["name"] = name
		taken.add(name)


def slugify(label: str | None) -> str | None:
	if not label:
		return None
	return re.sub(r"[^a-z0-9]+", "_", label.lower()).strip("_") or None


def get_meta_layout(dt: str) -> list:
	tabs = []
	for field in frappe.get_meta(dt).fields:
		if field.fieldtype == "Tab Break":
			tabs.append(new_container(field, "sections"))
		elif field.fieldtype == "Section Break":
			ensure_tab(tabs)["sections"].append(new_container(field, "columns"))
		elif field.fieldtype == "Column Break":
			ensure_section(tabs)["columns"].append(new_container(field, "fields"))
		else:
			ensure_column(tabs)["fields"].append(field.fieldname)
	return tabs


def new_container(field, children_key: str) -> dict:
	container = {"name": field.fieldname, children_key: []}
	if field.label:
		container["label"] = field.label
	return container


def ensure_tab(tabs: list) -> dict:
	if not tabs:
		tabs.append({"name": "first_tab", "sections": []})
	return tabs[-1]


def ensure_section(tabs: list) -> dict:
	tab = ensure_tab(tabs)
	if not tab["sections"]:
		tab["sections"].append({"name": "section_1", "columns": []})
	return tab["sections"][-1]


def ensure_column(tabs: list) -> dict:
	section = ensure_section(tabs)
	if not section["columns"]:
		section["columns"].append({"name": "column_1", "fields": []})
	return section["columns"][-1]
