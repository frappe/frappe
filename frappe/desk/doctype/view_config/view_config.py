# Copyright (c) 2024, Frappe Technologies and contributors
# For license information, please see license.txt

import json

import frappe
from frappe.core.doctype.doctype.doctype import get_fields_not_allowed_in_list_view
from frappe.desk.utils import slug
from frappe.model.document import Document


class ViewConfig(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		columns: DF.Code | None
		custom: DF.Check
		document_type: DF.Link | None
		filters: DF.JSON | None
		label: DF.Data | None
		sort_field: DF.Data | None
		sort_order: DF.Literal["ASC", "DESC"]
	# end: auto-generated types

	def autoname(self):
		self.name = slug(self.label)

	pass


def get_default_config(doctype: str) -> dict:
	if doc := frappe.db.exists("View Config", {"document_type": doctype, "custom": 0}):
		return frappe.get_doc("View Config", doc).as_dict()
	meta = frappe.get_meta(doctype)
	columns = []
	for field in meta.fields:
		if (field.in_list_view or field.fieldname == meta.sort_field) and field.fieldname != meta.image_field:
			columns.append(get_column_dict(field.as_dict()))

	if meta.sort_field in ["owner", "creation", "modified", "modified_by"]:
		for field in frappe.model.std_fields:
			if field.get("fieldname") == meta.sort_field:
				columns.append(get_column_dict(field))

	return {
		"document_type": doctype,
		"label": "List View",
		"columns": columns,
		"filters": [],
		"from_meta": True,
		"sort_field": meta.sort_field,
		"sort_order": meta.sort_order,
	}


@frappe.whitelist()
def get_config(doctype: str, config_name=None, is_default=True) -> dict:
	config_dict = (
		get_default_config(doctype) if is_default else frappe.get_doc("View Config", config_name).as_dict()
	)

	meta = frappe.get_meta(doctype)

	config_dict.update(
		{
			"columns": frappe.parse_json(config_dict.get("columns")),
			"filters": get_filters(config_dict.get("filters") or [], meta),
			"fields": get_doctype_fields(meta),
			"views": get_views_for_doctype(doctype),
			"title_field": get_title_field(meta),
			"sort": [config_dict.get("sort_field"), config_dict.get("sort_order")],
		}
	)

	return config_dict


def get_filters(filters: list[list], meta: dict) -> list[dict]:
	filter_dicts = []
	for filter in filters:
		field = meta.get_field(filter[0])
		filter_dicts.append(
			{
				"fieldname": filter[0],
				"fieldtype": field.fieldtype,
				"operator": filter[1],
				"value": filter[2],
				"options": field.options.split("\n") if field.options else [],
			}
		)
	return filter_dicts


def get_doctype_fields(meta: dict) -> list[dict]:
	not_allowed_in_list_view = get_fields_not_allowed_in_list_view(meta)
	doctype_fields = []
	for field in meta.fields + frappe.model.std_fields:
		if field.get("fieldtype") in not_allowed_in_list_view:
			continue
		options = field.get("options") or ""
		doctype_fields.append(
			{
				"label": field.get("label"),
				"key": field.get("fieldname"),
				"type": field.get("fieldtype"),
				"options": options.split("\n"),
			}
		)
	return doctype_fields


def get_column_dict(field: dict) -> dict:
	field = frappe._dict(field)
	return {
		"label": field.label,
		"key": field.fieldname,
		"type": field.fieldtype,
		"options": field.options,
		"width": "10rem",
	}


@frappe.whitelist()
def get_views_for_doctype(doctype: str) -> list[dict]:
	return frappe.get_all(
		"View Config",
		filters={"document_type": doctype, "custom": 1},
		fields=["name", "label", "icon"],
		order_by="modified desc",
		limit=6,
	)


@frappe.whitelist()
def update_config(config: dict, doctype=None, config_name=None, filters=None) -> dict:
	config = frappe._dict(config)
	if config_name:
		doc = frappe.get_doc("View Config", config_name)
	else:
		doc = frappe.new_doc("View Config")
		doc.label = f"{doctype} List View"
		doc.document_type = doctype
		doc.custom = 0
	if filters:
		doc.filters = json.dumps(filters)
	doc.columns = json.dumps(config.columns)
	doc.sort_field = config.sort[0]
	doc.sort_order = config.sort[1]
	return doc.save()


@frappe.whitelist()
def reset_default_config(config_name: str) -> None:
	frappe.delete_doc("View Config", config_name)


@frappe.whitelist()
def get_link_title_field(doctype: str, name: str) -> str:
	meta = frappe.get_meta(doctype)
	if not meta.show_title_field_in_link:
		return name
	return frappe.get_value(doctype, name, meta.title_field) or name


@frappe.whitelist()
def get_list(doctype: str, cols: list[dict], filters: list[list], limit: int, order_by: str) -> list[dict]:
	fields = [col.get("key") for col in cols] + [get_title_field(doctype)[1]]
	list_rows = frappe.get_list(
		doctype, fields=fields, filters=filters, limit=limit, start=0, order_by=order_by
	)
	if not list_rows:
		return []
	return get_list_rows(cols, list_rows)


def get_list_rows(cols: list[dict], list_rows: list[dict]) -> list[dict]:
	link_fields = [field for field in cols if field.get("type") == "Link"]
	for row in list_rows:
		for link_field in link_fields:
			dt = link_field.get("options")
			key = link_field.get("key")
			row[key] = get_link_title_field(dt, row[key])
	return list_rows


def get_title_field(meta: dict) -> tuple[str, str]:
	if isinstance(meta, str):
		meta = frappe.get_meta(meta)
	return [meta.title_field, meta.image_field or ""]


@frappe.whitelist()
def rename_config(config_name: str, new_name: str) -> str:
	configSlug = slug(new_name)
	frappe.rename_doc("View Config", config_name, configSlug)
	frappe.db.set_value("View Config", configSlug, "label", new_name)
	return configSlug
