# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe


def execute():
	if frappe.db.exists("DocType", "Event Producer"):
		frappe.db.sql("""UPDATE `tabEvent Producer` SET api_key='', api_secret=''""")
	if frappe.db.exists("DocType", "Event Consumer"):
		frappe.db.sql("""UPDATE `tabEvent Consumer` SET api_key='', api_secret=''""")
