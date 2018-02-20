# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.utils import get_number_format_info

def execute():
	frappe.reload_doc('core', 'doctype', 'system_settings', force=True)
	if not frappe.db.get_value("System Settings", None, "currency_precision"):
		default_currency = frappe.db.get_default("currency")
		number_format = frappe.db.get_value("Currency", default_currency, "number_format") \
			or frappe.db.get_default("number_format")
		if number_format:
			precision = get_number_format_info(number_format)[2]
		else:
			precision = 2

		ss = frappe.get_doc("System Settings")
		ss.currency_precision = precision
		ss.flags.ignore_mandatory = True
		ss.save()
