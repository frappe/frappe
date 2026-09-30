# Copyright (c) 2018, Frappe Technologies and contributors
# License: MIT. See LICENSE

import json
import os

import frappe
from frappe import _
from frappe.model import std_fields
from frappe.model.document import Document
from frappe.modules.utils import get_module_path
from frappe.utils import cstr, strip_html


class ListFilter(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		columns: DF.LongText | None
		filter_name: DF.Data | None
		filters: DF.LongText | None
		for_user: DF.Link | None
		is_standard: DF.Check
		module: DF.Link | None
		reference_doctype: DF.Link | None
		route_signature: DF.SmallText | None
		sort_field: DF.Data | None
		sort_order: DF.Data | None
	# end: auto-generated types

	def autoname(self):
		# Standard layouts sync by name, so it must be the same on every site.
		if self.is_standard:
			self.name = f"{self.reference_doctype}-{_clean_filter_name(self.filter_name)}"

	def validate(self):
		if self.is_standard or self._was_standard():
			self.validate_standard()

		if not self.for_user:
			if not _can_edit_global_filter():
				frappe.throw(
					_("You are not allowed to create or edit global layouts"), frappe.PermissionError
				)
			return

		if self.for_user != frappe.session.user and not _can_edit_global_filter():
			frappe.throw(_("You are not allowed to assign layouts to other users"), frappe.PermissionError)

	def validate_standard(self):
		if not frappe.conf.developer_mode and not frappe.flags.in_migrate:
			frappe.throw(
				_("Standard list layouts can only be changed in developer mode"), frappe.PermissionError
			)

		if not self.is_standard:
			return

		if not self.is_new() and not self._was_standard():
			frappe.throw(_("Only a new list layout can be made standard"))

		if self.for_user:
			frappe.throw(_("A standard list layout cannot belong to a user"))

		if not (self.filter_name and self.reference_doctype and self.module):
			frappe.throw(
				_("Filter Name, Reference Document Type and Module are required for a standard list layout"),
				frappe.MandatoryError,
			)

	def _was_standard(self) -> bool:
		before = self.get_doc_before_save()
		return bool(before and before.is_standard)

	def before_save(self):
		if self.filter_name:
			self.filter_name = _clean_filter_name(self.filter_name)

		if self.reference_doctype:
			valid_fields = _get_valid_filter_fields(self.reference_doctype)
			if self.filters:
				parsed_filters = frappe.parse_json(self.filters)
				self.filters = json.dumps(_sanitize_filters(parsed_filters, valid_fields))
			if self.columns:
				parsed_columns = frappe.parse_json(self.columns)
				self.columns = json.dumps(_sanitize_columns(parsed_columns, valid_fields))
			self.sort_field, self.sort_order = _sanitize_sorting(
				self.sort_field, self.sort_order, valid_fields
			)

		self.route_signature = compute_route_signature(self.reference_doctype, self.filters)

	def on_update(self):
		if self.is_standard and frappe.conf.developer_mode and not frappe.flags.in_import:
			self.export_layout()

	def on_trash(self):
		if not self.is_standard or frappe.flags.in_migrate:
			return

		if not frappe.conf.developer_mode:
			frappe.throw(
				_("Standard list layouts can only be deleted in developer mode"), frappe.PermissionError
			)

		# Otherwise the next migrate brings the layout back.
		path = self.get_export_path()
		if os.path.exists(path):
			os.remove(path)

	def get_export_path(self) -> str:
		"""Kept with the DocType it belongs to: doctype/{reference_doctype}/list_filter/{name}.json"""
		return os.path.join(
			get_module_path(self.module),
			"doctype",
			frappe.scrub(self.reference_doctype),
			"list_filter",
			f"{frappe.scrub(self.name)}.json",
		)

	def export_layout(self):
		path = self.get_export_path()
		frappe.create_folder(os.path.dirname(path))
		with open(path, "w+") as f:  # nosemgrep
			f.write(frappe.as_json(self.as_dict(no_nulls=True, no_private_properties=True)) + "\n")


def _clean_filter_name(filter_name: str | None) -> str:
	return strip_html(cstr(filter_name)).strip()


def compute_route_signature(reference_doctype: str | None, filters) -> str:
	"""Build a stable query-string signature from saved filter tuples (matches list view URL encoding)."""
	if isinstance(filters, str):
		filters = frappe.parse_json(filters) or []
	if not isinstance(filters, list) or not reference_doctype:
		return ""

	params: list[tuple[str, str]] = []
	for row in filters:
		if not isinstance(row, (list, tuple)) or len(row) < 4:
			continue
		doctype, field, operator, value = row[0], row[1], row[2], row[3]
		query_key = cstr(field) if doctype == reference_doctype else f"{doctype}.{field}"
		if operator == "=":
			query_value = cstr(value)
		else:
			query_value = json.dumps([operator, value], separators=(",", ":"))
		params.append((query_key, query_value))

	params.sort(key=lambda item: (item[0], item[1]))
	return "&".join(f"{key}={value}" for key, value in params)


def _can_edit_global_filter() -> bool:
	return frappe.session.user == "Administrator" or "System Manager" in frappe.get_roles()


def _can_update_list_filter(doc: Document) -> bool:
	if not doc.for_user:
		return _can_edit_global_filter()
	return doc.for_user == frappe.session.user


def _get_valid_filter_fields(reference_doctype: str) -> set[str]:
	meta = frappe.get_meta(reference_doctype)
	valid_fields = {field["fieldname"] for field in std_fields}
	valid_fields.add("status_field")
	valid_fields.update(df.fieldname for df in meta.fields)
	return valid_fields


def _sanitize_filters(filters, valid_fields: set[str]) -> list:
	if not isinstance(filters, list):
		return []
	return [
		row for row in filters if isinstance(row, (list, tuple)) and len(row) > 1 and row[1] in valid_fields
	]


def _sanitize_columns(columns, valid_fields: set[str]) -> list:
	if not isinstance(columns, list):
		return []
	sanitized = []
	for col in columns:
		if not isinstance(col, dict):
			continue
		fieldname = col.get("fieldname")
		if fieldname == "status_field" or fieldname in valid_fields:
			sanitized.append(col)
	return sanitized


def _sanitize_sorting(sort_field, sort_order, valid_fields: set[str]) -> tuple[str | None, str | None]:
	if not sort_field or sort_field not in valid_fields:
		return None, None
	order = cstr(sort_order).lower()
	return sort_field, "asc" if order == "asc" else "desc"


@frappe.whitelist()
def update_list_filter(
	name: str,
	filter_name: str | None = None,
	for_user: str | None = None,
	filters: str | list | None = None,
	columns: str | list | None = None,
	sort_field: str | None = None,
	sort_order: str | None = None,
):
	"""Update saved filter state with permission checks."""
	doc = frappe.get_doc("List Filter", name)

	if not _can_update_list_filter(doc):
		if not doc.for_user:
			frappe.throw(_("You are not allowed to update global layouts"), frappe.PermissionError)
		frappe.throw(_("You are not allowed to update this layout"), frappe.PermissionError)

	if filter_name is not None:
		doc.filter_name = cstr(filter_name).strip()

	if for_user is not None:
		next_for_user = cstr(for_user)
		if not next_for_user and not _can_edit_global_filter():
			frappe.throw(_("You are not allowed to update global layouts"), frappe.PermissionError)
		if next_for_user and next_for_user != frappe.session.user and not _can_edit_global_filter():
			frappe.throw(_("You are not allowed to assign layouts to other users"), frappe.PermissionError)
		doc.for_user = next_for_user

	if filters is not None:
		doc.filters = json.dumps(frappe.parse_json(filters) or [])

	if columns is not None:
		doc.columns = json.dumps(frappe.parse_json(columns) or [])

	if sort_field is not None:
		doc.sort_field = sort_field

	if sort_order is not None:
		doc.sort_order = sort_order

	doc.save(ignore_permissions=True)  # permissions checked via _can_update_list_filter above
	return doc.as_dict()


@frappe.whitelist()
def delete_list_filter(name: str):
	"""Delete a saved filter with permission checks."""
	doc = frappe.get_doc("List Filter", name)

	if not _can_update_list_filter(doc):
		if not doc.for_user:
			frappe.throw(_("You are not allowed to delete global layouts"), frappe.PermissionError)
		frappe.throw(_("You are not allowed to delete this layout"), frappe.PermissionError)

	doc.delete(ignore_permissions=True)  # permissions checked via _can_update_list_filter above
	return True


# Backward compatibility for older clients during rollout.
@frappe.whitelist()
def update_list_layout(name: str, **kwargs):
	if "layout_name" in kwargs and "filter_name" not in kwargs:
		kwargs["filter_name"] = kwargs.pop("layout_name")
	return update_list_filter(name, **kwargs)


@frappe.whitelist()
def delete_list_layout(name: str):
	return delete_list_filter(name)
