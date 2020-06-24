# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
import datetime
from frappe.utils import formatdate, fmt_money, flt, cstr, cint, format_datetime, format_time, format_duration
from frappe.model.meta import get_field_currency, get_field_precision
import re
from six import string_types

def format_value(value, df=None, doc=None, currency=None, translated=False):
	'''Format value based on given fieldtype, document reference, currency reference.
	If docfield info (df) is not given, it will try and guess based on the datatype of the value'''
	if isinstance(df, string_types):
		df = frappe._dict(fieldtype=df)

	if not df:
		df = frappe._dict()
		if isinstance(value, datetime.datetime):
			df.fieldtype = 'Datetime'
		elif isinstance(value, datetime.date):
			df.fieldtype = 'Date'
		elif isinstance(value, datetime.timedelta):
			df.fieldtype = 'Time'
		elif isinstance(value, int):
			df.fieldtype = 'Int'
		elif isinstance(value, float):
			df.fieldtype = 'Float'
		else:
			df.fieldtype = 'Data'

	elif (isinstance(df, dict)):
		# Convert dict to object if necessary
		df = frappe._dict(df)

	if value is None:
		value = ""
	elif translated:
		value = frappe._(value)

	if not df:
		return value

	elif df.get("fieldtype")=="Date":
		return formatdate(value)

	elif df.get("fieldtype")=="Datetime":
		return format_datetime(value)

	elif df.get("fieldtype")=="Time":
		return format_time(value)

	elif value==0 and df.get("fieldtype") in ("Int", "Float", "Currency", "Percent") and df.get("print_hide_if_no_value"):
		# this is required to show 0 as blank in table columns
		return ""

	elif df.get("fieldtype") == "Currency":
		default_currency = frappe.db.get_default("currency")
		currency = currency or get_field_currency(df, doc) or default_currency
		return fmt_money(value, precision=get_field_precision(df, doc), currency=currency)

	elif df.get("fieldtype") == "Float":
		precision = get_field_precision(df, doc)
		# I don't know why we support currency option for float
		currency = currency or get_field_currency(df, doc)

		# show 1.000000 as 1
		# options should not specified
		if not df.options and value is not None:
			temp = cstr(value).split(".")
			if len(temp)==1 or cint(temp[1])==0:
				precision = 0

		return fmt_money(value, precision=precision, currency=currency)

	elif df.get("fieldtype") == "Percent":
		return "{}%".format(flt(value, 2))

	elif df.get("fieldtype") in ("Text", "Small Text"):
		if not re.search("(\<br|\<div|\<p)", value):
			return frappe.safe_decode(value).replace("\n", "<br>")

	elif df.get("fieldtype") == "Markdown Editor":
		return frappe.utils.markdown(value)

	elif df.get("fieldtype") == "Table MultiSelect":
		meta = frappe.get_meta(df.options)
		link_field = [df for df in meta.fields if df.fieldtype == 'Link'][0]
		values = [v.get(link_field.fieldname, 'asdf') for v in value]
		return ', '.join(values)

	elif df.get("fieldtype") == "Duration":
		hide_days = df.hide_days
		return format_duration(value, hide_days)

	return value
