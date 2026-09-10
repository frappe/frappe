# Copyright (c) 2026, Frappe Technologies Pvt Ltd and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.naming import append_number_if_name_exists
from frappe.utils import cint

from studio.export import can_export, parse_json
from studio.studio.doctype.studio_component.studio_component import fetch_component_batch

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
COMPONENT_INPUT_FIELDS = ("input_name", "type", "required", "default", "description", "options")


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
	app_name: str,
	components=None,
	files=None,
	page_name: str | None = None,
	resources=None,
	variables=None,
	overwrite_conflicts: bool = False,
):
	"""Install missing paste dependencies and report names whose target definitions differ."""
	app = get_writable_app(app_name)
	page = get_writable_page(page_name, app.name) if page_name else None
	resources = parse_dict_list(resources, "resources")
	variables = parse_dict_list(variables, "variables")
	conflicts = {
		"components": install_dependencies(app, components, files, overwrite_conflicts=overwrite_conflicts)
	}
	if page_name:
		conflicts.update(add_page_data(page, resources, variables, overwrite_conflicts=overwrite_conflicts))
	return {"conflicts": conflicts, "modified": page.modified if page else None}


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
	page.check_permission("read")
	page.check_permission("write")
	if page.studio_app != app_name:
		frappe.throw(_("The target page does not belong to the selected app."), frappe.PermissionError)
	return page


def install_dependencies(app, components, files, *, overwrite_conflicts=False):
	conflicts = create_missing_components(
		parse_dict_list(components, "components"), overwrite_conflicts=overwrite_conflicts
	)
	if can_export(app):
		app.write_files(parse_dict_list(files, "files"))
	return conflicts


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


def add_page_data(page, resources: list[dict], variables: list[dict], *, overwrite_conflicts=False):
	conflicts = {}
	conflicts["resources"], resources_changed = append_missing_rows(
		page,
		"resources",
		resources,
		"resource_name",
		PAGE_RESOURCE_FIELDS,
		int_fields=PAGE_RESOURCE_INT_FIELDS,
		json_fields=PAGE_RESOURCE_JSON_FIELDS,
		overwrite_conflicts=overwrite_conflicts,
	)
	conflicts["variables"], variables_changed = append_missing_rows(
		page,
		"variables",
		variables,
		"variable_name",
		PAGE_VARIABLE_FIELDS,
		overwrite_conflicts=overwrite_conflicts,
	)
	if resources_changed or variables_changed:
		page.save()
	return conflicts


def append_missing_rows(
	page,
	table_field,
	rows,
	key_field,
	fields,
	*,
	int_fields=(),
	json_fields=(),
	overwrite_conflicts=False,
):
	"""Add absent rows and return different same-name definitions for conflict review."""
	existing = {row.get(key_field): row for row in page.get(table_field)}
	conflicts = []
	changed = False
	for row in rows:
		if not isinstance(row, dict) or not isinstance(row.get(key_field), str):
			frappe.throw(_("Invalid {0} in copied content.").format(key_field.replace("_", " ")))
		key = row[key_field]
		if key in existing:
			if dependency_signature(existing[key], fields, int_fields, json_fields) != dependency_signature(
				row, fields, int_fields, json_fields
			):
				conflicts.append(
					{"name": key, "existing": pick(existing[key], fields), "copied": pick(row, fields)}
				)
				if overwrite_conflicts:
					existing[key].update(pick(row, fields))
					changed = True
			continue
		existing[key] = page.append(table_field, pick(row, fields))
		changed = True
	return conflicts, changed


def dependency_signature(row, fields, int_fields=(), json_fields=()):
	def normalize(field):
		value = row.get(field)
		if field in int_fields:
			return cint(value)
		if field in json_fields:
			return frappe.parse_json(value) if value else None
		return value if value not in (None, "") else None

	return {field: normalize(field) for field in fields}


def pick(row, fields) -> dict:
	return {field: row.get(field) for field in fields}


def create_missing_components(components: list[dict], *, overwrite_conflicts=False):
	for component in components:
		validate_component_copy(component)
	if not components:
		return []

	frappe.has_permission("Studio Component", ptype="read", throw=True)
	existing_by_name = {
		component.name: component
		for component in fetch_component_batch({component["name"] for component in components})
	}
	conflicts = []
	for component in components:
		existing = existing_by_name.get(component["name"])

		if not existing:
			new_component_from_copy(component).insert()
			continue

		if component_signature(existing) == component_signature(component):
			continue
		conflicts.append(
			{
				"name": component["component_name"],
				"existing": get_component_copy(existing),
				"copied": get_component_copy(component),
			}
		)
		if overwrite_conflicts:
			existing = frappe.get_doc("Studio Component", component["name"])
			update_component_from_copy(existing, component).save()
	return conflicts


def component_signature(component):
	return {
		"component_name": component.get("component_name"),
		"block": frappe.parse_json(component.get("block")),
		"is_disabled": cint(component.get("is_disabled")),
		"inputs": [
			dependency_signature(row, COMPONENT_INPUT_FIELDS, int_fields={"required"})
			for row in component.get("inputs") or []
		],
	}


def get_component_copy(component):
	return {
		"name": component.get("name"),
		"component_id": component.get("component_id"),
		"component_name": component.get("component_name"),
		"block": component.get("block"),
		"is_disabled": component.get("is_disabled"),
		"inputs": [pick(row, COMPONENT_INPUT_FIELDS) for row in component.get("inputs") or []],
	}


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
	return update_component_from_copy(
		frappe.get_doc(
			doctype="Studio Component",
			component_id=component["component_id"],
		),
		component,
	)


def update_component_from_copy(doc, component):
	doc.component_name = component["component_name"]
	doc.block = component["block"]
	doc.is_disabled = component.get("is_disabled")
	doc.set(
		"inputs",
		[{**pick(row, COMPONENT_INPUT_FIELDS), "name": None} for row in component.get("inputs") or []],
	)
	return doc


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
