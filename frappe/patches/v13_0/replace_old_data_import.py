# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	if not frappe.db.exists("DocType", "Data Import Beta"):
		return

	frappe.db.sql("DROP TABLE IF EXISTS `tabData Import Legacy`")
	frappe.rename_doc('DocType', 'Data Import', 'Data Import Legacy')
	frappe.db.commit()
	frappe.db.sql("DROP TABLE IF EXISTS `tabData Import`")
	frappe.rename_doc('DocType', 'Data Import Beta', 'Data Import')
