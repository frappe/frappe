# Copyright (c) 2026, Frappe Technologies and contributors
# For license information, please see license.txt

import json
from secrets import token_urlsafe

import frappe
from frappe import _
from frappe.model.document import Document
from frappe.utils import cint, get_datetime, now_datetime


class InvalidFieldsInValuesError(frappe.ValidationError):
	def __init__(self, message: str, *, invalid_fields: tuple[str, ...]):
		super().__init__(message)
		self.invalid_fields = invalid_fields


class IllegalReferenceDocnameForMultipleResponsesError(frappe.ValidationError):
	pass


class WebFormRequest(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		doc_values: DF.Code | None
		expires_on: DF.Datetime | None
		key: DF.Data | None
		reference_docname: DF.DynamicLink | None
		reference_doctype: DF.Link | None
		used_on: DF.Datetime | None
		web_form: DF.Link
		web_form_values: DF.Code | None
	# end: auto-generated types

	def before_insert(self):
		self.key = self.key or token_urlsafe()

	def validate(self):
		if not self.web_form:
			return

		web_form = frappe.get_doc("Web Form", self.web_form)
		self.reference_doctype = web_form.doc_type

		if cint(web_form.allow_multiple) and self.reference_docname:
			frappe.throw(
				_("Reference Docname cannot be set when the Web Form allows multiple responses"),
				IllegalReferenceDocnameForMultipleResponsesError,
			)

		if self.web_form_values:
			validate_web_form_values(web_form, parse_json_object(self.web_form_values))

		if self.doc_values:
			validate_doc_values(self.reference_doctype, parse_json_object(self.doc_values))

	def validate_key(self, *, allow_used=False):
		if self.used_on and not allow_used:
			frappe.throw(_("This Web Form Request has already been used"), frappe.exceptions.LinkExpired)

		if self.expires_on and get_datetime(self.expires_on) < now_datetime():
			frappe.throw(_("This Web Form Request has expired"), frappe.exceptions.LinkExpired)

	def get_web_form_values(self):
		return parse_json_object(self.web_form_values)

	def get_doc_values(self):
		return parse_json_object(self.doc_values)


def parse_json_object(json_string: str | None):
	if not json_string:
		return {}

	try:
		values = json.loads(json_string)
	except json.JSONDecodeError:
		frappe.throw(_("Invalid JSON"))

	if not isinstance(values, dict):
		frappe.throw(_("JSON value must be an object"))

	return values


def validate_json_object(json_string: str):
	parse_json_object(json_string)


def validate_web_form_values(web_form, values: dict):
	valid_fields = {field.fieldname for field in web_form.web_form_fields if field.fieldname}
	validate_value_fields(values, valid_fields, _("Web Form Values"))


def validate_doc_values(doctype: str, values: dict):
	meta = frappe.get_meta(doctype)
	valid_fields = {field.fieldname for field in meta.fields if field.fieldname}
	validate_value_fields(values, valid_fields, _("Doc Values"))


def validate_value_fields(values: dict, valid_fields: set[str], label: str):
	invalid_fields = sorted(set(values) - valid_fields)
	if invalid_fields:
		msg = _("{0} contains invalid field(s): {1}").format(label, ", ".join(invalid_fields))
		frappe.throw(
			msg,
			InvalidFieldsInValuesError(msg, invalid_fields=tuple(invalid_fields)),
		)


def get_web_form_request(
	web_form: str, key: str | None, *, for_update=False, required=False, allow_used=False
):
	if not key:
		if required:
			frappe.throw(_("Web Form Request key is required"), frappe.PermissionError)
		return

	request_name = frappe.db.get_value(
		"Web Form Request",
		{
			"web_form": web_form,
			"key": key,
		},
		"name",
	)
	if not request_name:
		frappe.throw(_("Invalid Web Form Request"), frappe.PermissionError)

	web_form_request = frappe.get_doc("Web Form Request", request_name, for_update=for_update)
	web_form_request.validate_key(allow_used=allow_used)
	return web_form_request
