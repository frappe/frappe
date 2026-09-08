# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.database import savepoint
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import cint

from studio.export import can_export, parse_json

PAGE_RESOURCE_FIELDS = (
	"resource_type",
	"resource_name",
	"auto",
	"fields",
	"filters",
	"limit",
	"sort_field",
	"sort_order",
	"document_type",
	"document_name",
	"fetch_document_using_filters",
	"url",
	"method",
	"params",
	"whitelisted_methods",
	"transform",
	"on_success",
	"on_error",
)
PAGE_VARIABLE_FIELDS = ("variable_name", "variable_type", "initial_value")
PAGE_RESOURCE_INT_FIELDS = {"auto", "limit", "fetch_document_using_filters"}
PAGE_RESOURCE_JSON_FIELDS = {"fields", "filters", "params", "whitelisted_methods"}


@frappe.whitelist()
def duplicate_page(page_name: str, app_name: str | None):
	page = frappe.get_doc("Studio Page", page_name)
	page.check_permission("read")
	blocks = parse_json(page.draft_blocks or page.blocks) or []
	return paste_page(app_name or page.studio_app, {**page.get_copy(blocks), "blocks": blocks})


@frappe.whitelist()
def paste_page(app_name: str, page: dict | str, target_page: str | None = None):
	"""Create a page from a copy, or replace the contents of `target_page` with it."""
	copy = frappe.parse_json(page)
	if not isinstance(copy, dict):
		frappe.throw(_("Invalid page copy."))

	app = get_writable_app(app_name)
	blocks = parse_dict_list(copy.get("blocks"), "blocks")
	resources = parse_dict_list(copy.get("resources"), "resources")
	variables = parse_dict_list(copy.get("variables"), "variables")
	validate_page_copy(copy)
	if target_page:
		doc = get_writable_page(target_page, app.name)
	else:
		frappe.has_permission("Studio Page", ptype="create", throw=True)
		doc = new_page_from_copy(app, copy)
	install_dependencies(app, copy.get("components"), copy.get("files"))
	doc.draft_blocks = blocks
	doc.set("resources", [pick(row, PAGE_RESOURCE_FIELDS) for row in resources])
	doc.set("variables", [pick(row, PAGE_VARIABLE_FIELDS) for row in variables])
	doc.script = copy.get("script")
	doc.save()
	if can_export(doc):
		doc.write_script_file()
	return doc


@frappe.whitelist()
def create_missing_dependencies(
	app_name: str, components=None, files=None, page_name: str | None = None, resources=None, variables=None
):
	"""Give the app (and, for pasted blocks, the page) what a paste needs and doesn't have yet."""
	app = get_writable_app(app_name)
	page = get_writable_page(page_name, app.name) if page_name else None
	resources = parse_dict_list(resources, "resources")
	variables = parse_dict_list(variables, "variables")
	install_dependencies(app, components, files)
	if page_name:
		add_page_data(page, resources, variables)


def get_writable_app(app_name: str):
	if not isinstance(app_name, str) or not app_name:
		frappe.throw(_("Invalid Studio App."))
	app = frappe.get_doc("Studio App", app_name)
	app.check_permission("write")
	return app


def get_writable_page(page_name: str, app_name: str):
	if not isinstance(page_name, str) or not page_name:
		frappe.throw(_("Invalid Studio Page."))
	page = frappe.get_doc("Studio Page", page_name)
	page.check_permission("write")
	if page.studio_app != app_name:
		frappe.throw(_("The target page does not belong to the selected app."), frappe.PermissionError)
	return page


def install_dependencies(app, components, files):
	create_missing_components(parse_dict_list(components, "components"))
	if can_export(app):
		app.write_files(parse_dict_list(files, "files"))


def parse_list(value, label: str) -> list:
	value = frappe.parse_json(value)
	if value is None:
		return []
	if not isinstance(value, list):
		frappe.throw(_("Invalid {0} in copied content.").format(label))
	return value


def parse_dict_list(value, label: str) -> list[dict]:
	rows = parse_list(value, label)
	if not all(isinstance(row, dict) for row in rows):
		frappe.throw(_("Invalid {0} in copied content.").format(label))
	return rows


def validate_page_copy(copy: dict):
	if copy.get("page_title") is not None and not isinstance(copy["page_title"], str):
		frappe.throw(_("Invalid page title in copied content."))
	if copy.get("script") is not None and not isinstance(copy["script"], str):
		frappe.throw(_("Invalid script in copied content."))
	if copy.get("allow_guest") not in (None, 0, 1, False, True):
		frappe.throw(_("Invalid guest access setting in copied content."))


def add_page_data(page, resources: list[dict], variables: list[dict]):
	append_missing_rows(
		page,
		"resources",
		resources,
		"resource_name",
		PAGE_RESOURCE_FIELDS,
		int_fields=PAGE_RESOURCE_INT_FIELDS,
		json_fields=PAGE_RESOURCE_JSON_FIELDS,
	)
	append_missing_rows(page, "variables", variables, "variable_name", PAGE_VARIABLE_FIELDS)
	if page.has_value_changed("resources") or page.has_value_changed("variables"):
		page.save()


def append_missing_rows(page, table_field, rows, key_field, fields, int_fields=None, json_fields=None):
	existing = {row.get(key_field): row for row in page.get(table_field)}
	for row in rows:
		if not isinstance(row, dict) or not isinstance(row.get(key_field), str):
			frappe.throw(_("Invalid {0} in copied content.").format(key_field.replace("_", " ")))
		key = row[key_field]
		values = pick(row, fields)
		if key in existing:
			if row_signature(existing[key], fields, int_fields, json_fields) != row_signature(
				row, fields, int_fields, json_fields
			):
				frappe.throw(
					_("{0} already exists with a different definition.").format(key),
					title=_("Page data conflict"),
				)
			continue
		existing[key] = page.append(table_field, values)


def pick(row, fields) -> dict:
	return {field: row.get(field) for field in fields}


def row_signature(row, fields, int_fields=None, json_fields=None) -> dict:
	values = pick(row, fields)
	for field in int_fields or ():
		values[field] = cint(values[field])
	for field in json_fields or ():
		if values[field]:
			values[field] = frappe.parse_json(values[field])
	return values


def create_missing_components(components: list[dict]):
	for component in components:
		validate_component_copy(component)
		if frappe.db.exists("Studio Component", component["name"]):
			ensure_component_matches(component)
			continue

		created = False
		# The unique component ID resolves a concurrent paste after the optimistic read.
		with savepoint(frappe.DuplicateEntryError):
			new_component_from_copy(component).insert()
			created = True
		if not created:
			ensure_component_matches(component)


def validate_component_copy(component):
	if not isinstance(component, dict):
		frappe.throw(_("Invalid component in copied content."))
	component_id = component.get("component_id")
	if not isinstance(component_id, str) or component.get("name") != component_id:
		frappe.throw(_("Invalid component ID in copied content."))
	if not isinstance(component.get("component_name"), str) or not isinstance(
		component.get("block"), str | dict
	):
		frappe.throw(_("Invalid component definition in copied content."))
	if not isinstance(component.get("inputs") or [], list) or not all(
		isinstance(row, dict) for row in component.get("inputs") or []
	):
		frappe.throw(_("Invalid component inputs in copied content."))


def new_component_from_copy(component):
	return frappe.get_doc(
		doctype="Studio Component",
		component_id=component["component_id"],
		component_name=component["component_name"],
		block=component["block"],
		is_disabled=component.get("is_disabled"),
		inputs=[{**row, "name": None} for row in component.get("inputs") or []],
	)


def ensure_component_matches(component):
	existing = frappe.get_doc("Studio Component", component["name"])
	existing.check_permission("read")
	if component_signature(existing) != component_signature(component):
		frappe.throw(
			_("Component {0} already exists with a different definition.").format(component["name"]),
			title=_("Component conflict"),
		)


def component_signature(component) -> dict:
	block = component.get("block")
	if isinstance(block, str):
		block = frappe.parse_json(block)
	input_fields = ("input_name", "type", "description", "options", "required", "default")
	return {
		"component_id": component.get("component_id"),
		"component_name": component.get("component_name"),
		"block": block,
		"is_disabled": cint(component.get("is_disabled")),
		"inputs": [row_signature(row, input_fields, {"required"}) for row in component.get("inputs") or []],
	}


def new_page_from_copy(app, copy: dict):
	title = copy.get("page_title")
	if title and frappe.db.exists("Studio Page", {"studio_app": app.name, "page_title": title}):
		title = append_number_if_name_exists(
			"Studio Page",
			f"{title} Copy",
			fieldname="page_title",
			separator=" ",
			filters={"studio_app": app.name},
		)

	return frappe.get_doc(
		doctype="Studio Page",
		studio_app=app.name,
		page_title=title,
		allow_guest=cint(copy.get("allow_guest")),
		is_standard=app.is_standard,
		frappe_app=app.frappe_app,
	)
