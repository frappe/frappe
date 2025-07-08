from typing import Literal

import frappe
from frappe.model import display_fieldtypes, no_value_fields, table_fields


@frappe.whitelist()
def get_doctype_fields(doctype: str) -> list[dict]:
	fields = frappe.get_meta(doctype).fields
	# find the name field
	name_field = next((field for field in fields if field.fieldname == "name"), None)
	if not name_field:
		name_field = frappe._dict(
			{
				"fieldname": "name",
				"fieldtype": "Data",
				"label": "ID",
			}
		)
		fields.append(name_field)

	return [
		field
		for field in fields
		if field.fieldtype not in ((set(no_value_fields) | set(display_fieldtypes)) - set(table_fields))
	]


@frappe.whitelist()
def get_whitelisted_methods(doctype: str) -> list[str]:
	from frappe import is_whitelisted
	from frappe.model.base_document import get_controller

	controller = get_controller(doctype)
	whitelisted_methods = []

	for method in controller.__dict__:
		if callable(getattr(controller, method)):
			try:
				is_whitelisted(getattr(controller, method))
				whitelisted_methods.append(method)
			except Exception:
				# not whitelisted
				continue

	return whitelisted_methods


@frappe.whitelist()
def check_app_permission() -> bool:
	if frappe.session.user == "Administrator":
		return True
	if frappe.has_permission("Studio App", ptype="write") and frappe.has_permission(
		"Studio Page", ptype="write"
	):
		return True
	return False


@frappe.whitelist()
def get_app_components(app_name: str, field: Literal["blocks", "draft_blocks"] = "blocks") -> set[str]:
	import re

	from studio.constants import DEFAULT_COMPONENTS, NON_VUE_COMPONENTS

	filters = dict(studio_app=app_name, published=1)
	filters[field] = ("is", "set")

	pages = frappe.get_all(
		"Studio Page",
		filters=filters,
		pluck=field,
	)
	if not pages:
		return set()
	components = set(DEFAULT_COMPONENTS)

	def add_h_function_components(text: str) -> set[str]:
		"""Extract component names from h(ComponentName...) function calls"""
		pattern = r"\bh\(\s*([A-Z][a-zA-Z0-9_]*)"

		matches = re.findall(pattern, text)
		for match in matches:
			components.add(match)

	def add_block_components(block: dict):
		if block.get("componentName") not in NON_VUE_COMPONENTS:
			components.add(block.get("componentName"))
		for child in block.get("children", []):
			add_block_components(child)

		if slots := block.get("componentSlots"):
			for slot in slots.values():
				if isinstance(slot.get("slotContent"), str):
					continue
				for slot_child in slot.get("slotContent"):
					add_block_components(slot_child)

	for blocks in pages:
		if not blocks:
			continue
		if isinstance(blocks, str):
			add_h_function_components(blocks)
			blocks = frappe.parse_json(blocks)
		root_block = blocks[0]
		add_block_components(root_block)

	return components
