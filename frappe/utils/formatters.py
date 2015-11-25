# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import formatdate, fmt_money, flt, cstr, cint, format_datetime
from frappe.model.meta import get_field_currency, get_field_precision
import re

def format_value(value, df, doc=None, currency=None):
	# Convert dict to object if necessary
	if (isinstance(df, dict)):
		df = frappe._dict(df)

	if value is None:
		value = ""

	if not df:
		return value

	elif df.get("fieldtype")=="Date":
		return formatdate(value)

	elif df.get("fieldtype")=="Datetime":
		return format_datetime(value)

	elif value==0 and df.get("fieldtype") in ("Int", "Float", "Currency", "Percent") and df.get("print_hide_if_no_value"):
		# this is required to show 0 as blank in table columns
		return ""

	elif df.get("fieldtype") == "Currency" or (df.get("fieldtype")=="Float" and (df.options or "").strip()):
		return fmt_money(value, precision=get_field_precision(df, doc),
			currency=currency if currency else (get_field_currency(df, doc) if doc else None))

	elif df.get("fieldtype") == "Float":
		precision = get_field_precision(df, doc)

		# show 1.000000 as 1
		# options should not specified
		if not df.options and value is not None:
			temp = cstr(value).split(".")
			if len(temp)==1 or cint(temp[1])==0:
				precision = 0

		return fmt_money(value, precision=precision)

	elif df.get("fieldtype") == "Percent":
		return "{}%".format(flt(value, 2))

	elif df.get("fieldtype") in ("Text", "Small Text"):
		if not re.search("(\<br|\<div|\<p)", value):
			return value.replace("\n", "<br>")

	return value
