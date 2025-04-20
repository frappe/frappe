# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import datetime
import re

from dateutil.parser import ParserError

import frappe
from frappe.model.meta import get_field_currency, get_field_precision
from frappe.utils import (
	cint,
	cstr,
	flt,
	fmt_money,
	format_datetime,
	format_duration,
	format_time,
	format_timedelta,
	formatdate,
)

BLOCK_TAGS_PATTERN = re.compile(r"(<br|<div|<p)")


def format_value(value, df=None, doc=None, currency=None, translated=False, format=None):
	"""
	Format value based on given fieldtype, document reference, currency reference.
	If docfield info (df) is not given, it will try and guess based on the datatype of the value.

	:param value: Value to be formatted.
	:param df: (Optional) DocField object with properties `fieldtype`, `options` etc.
	"""
	if isinstance(df, str):
		df = frappe._dict(fieldtype=df)

	if not df:
		df = frappe._dict()
		if isinstance(value, datetime.datetime):
			df.fieldtype = "Datetime"
		elif isinstance(value, datetime.date):
			df.fieldtype = "Date"
		elif isinstance(value, datetime.timedelta):
			df.fieldtype = "Time"
		elif isinstance(value, int):
			df.fieldtype = "Int"
		elif isinstance(value, float):
			df.fieldtype = "Float"
		else:
			df.fieldtype = "Data"

	elif isinstance(df, dict):
		# Convert dict to object if necessary
		df = frappe._dict(df)

	if value is None:
		value = ""
	elif translated:
		value = frappe._(value)

	if not df:
		return value

	elif df.get("fieldtype") == "Date":
		return formatdate(value)

	elif df.get("fieldtype") == "Datetime":
		return format_datetime(value)

	elif df.get("fieldtype") == "Time":
		try:
			return format_time(value)
		except ParserError:
			return format_timedelta(value)

	elif (
		value == 0
		and df.get("fieldtype") in ("Int", "Float", "Currency", "Percent")
		and df.get("print_hide_if_no_value")
	):
		# this is required to show 0 as blank in table columns
		return ""

	elif df.get("fieldtype") == "Currency":
		default_currency = frappe.db.get_default("currency")
		currency = currency or get_field_currency(df, doc) or default_currency
		return fmt_money(value, precision=get_field_precision(df, doc), currency=currency, format=format)

	elif df.get("fieldtype") == "Float":
		precision = get_field_precision(df, doc)
		# I don't know why we support currency option for float
		currency = currency or get_field_currency(df, doc)

		# show 1.000000 as 1
		# options should not specified
		if not df.options and value is not None:
			temp = cstr(value).split(".")
			if len(temp) == 1 or cint(temp[1]) == 0:
				precision = 0

		return fmt_money(value, precision=precision, currency=currency)

	elif df.get("fieldtype") == "Percent":
		return f"{flt(value, 2)}%"

	elif df.get("fieldtype") in ("Text", "Small Text"):
		if not BLOCK_TAGS_PATTERN.search(value):
			return frappe.safe_decode(value).replace("\n", "<br>")

	elif df.get("fieldtype") == "Markdown Editor":
		return frappe.utils.markdown(value)

	elif df.get("fieldtype") == "Table MultiSelect":
		values = []
		meta = frappe.get_meta(df.options)
		link_field = next(df for df in meta.fields if df.fieldtype == "Link")
		for v in value:
			v.update({"__link_titles": doc.get("__link_titles")})
			formatted_value = format_value(v.get(link_field.fieldname, ""), link_field, v)
			values.append(formatted_value)

		return ", ".join(values)

	elif df.get("fieldtype") == "Duration":
		hide_days = df.hide_days
		return format_duration(value, hide_days)

	elif df.get("fieldtype") == "Text Editor":
		return f"<div class='ql-snow'>{value}</div>"

	elif df.get("fieldtype") in ["Link", "Dynamic Link"]:
		if not doc or not doc.get("__link_titles") or not df.options:
			return value

		doctype = df.options
		if df.get("fieldtype") == "Dynamic Link":
			if not df.parent:
				return value

			meta = frappe.get_meta(df.parent)
			_field = meta.get_field(df.options)
			doctype = _field.options

		return doc.__link_titles.get(f"{doctype}::{value}", value)

	elif df.get("fieldtype") == "Select":
		if isinstance(value, str):
			return frappe._(value, context=df.parent or "")

	return value
