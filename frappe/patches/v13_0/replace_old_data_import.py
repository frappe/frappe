# Copyright (c) 2020, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe


def execute():
	frappe.rename_doc('DocType', 'Data Import', 'Data Import Legacy')
	frappe.db.commit()
	frappe.db.sql("DROP TABLE IF EXISTS `tabData Import`")
	frappe.reload_doc("core", "doctype", "data_import")
	frappe.get_doc("DocType", "Data Import").on_update()
	frappe.delete_doc_if_exists("DocType", "Data Import Beta")
