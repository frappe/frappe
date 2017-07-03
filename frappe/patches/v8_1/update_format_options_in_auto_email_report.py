# Copyright (c) 2017, Frappe and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	""" change the XLS option as XLSX in the auto email report """

	auto_email_list = frappe.get_all("Auto Email Report", filters={"format": "XLS"})
	for auto_email in auto_email_list:
		doc = frappe.get_doc("Auto Email Report", auto_email.name)
		doc.format = "XLSX"
		doc.save()
