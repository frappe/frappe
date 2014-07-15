# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
from frappe.utils import formatdate, fmt_money
from frappe.model.meta import get_field_currency, get_field_precision

def format_value(value, df, doc=None):
	if df.fieldtype=="Date":
		return formatdate(value)

	elif df.fieldtype == "Currency":
		return fmt_money(value, precision=get_field_precision(df, doc), currency=get_field_currency(df, doc))

	elif df.fieldtype == "Float":
		return fmt_money(value)

	elif df.fieldtype == "Percent":
		return "{}%".format(flt(value, 2))

	return value

