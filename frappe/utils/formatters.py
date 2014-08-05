# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from frappe.utils import formatdate, fmt_money, flt
from frappe.model.meta import get_field_currency, get_field_precision
import re

def format_value(value, df, doc=None, currency=None):
	if df.fieldtype=="Date":
		return formatdate(value)

	elif df.fieldtype == "Currency":
		return fmt_money(value, precision=get_field_precision(df, doc),
			currency=currency if currency else (get_field_currency(df, doc) if doc else None))

	elif df.fieldtype == "Float":
		return fmt_money(value, precision=get_field_precision(df, doc))

	elif df.fieldtype == "Percent":
		return "{}%".format(flt(value, 2))

	if value is None:
		value = ""

	if df.fieldtype in ("Text", "Small Text"):
		if not re.search("(\<br|\<div|\<p)", value):
			return value.replace("\n", "<br>")

	return value

