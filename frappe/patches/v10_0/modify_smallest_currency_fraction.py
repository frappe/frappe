# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	frappe.db.set_value('Currency', 'USD', 'smallest_currency_fraction_value', '0.01')