# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	for doctype in ['Page', 'Report']:
		for data in frappe.get_all(doctype, fields = ["name"]):
			doc = frappe.get_doc(doctype, data.name)
			make_custom_roles_for_page_and_report(doc, doctype)

def make_custom_roles_for_page_and_report(doc, doctype):
	field = doctype.lower()
	roles = [{'role': d.role} for d in doc.roles]
	if roles:
		custom_permission = frappe.get_doc({
			'doctype': 'Custom Role',
			field : doc.name,
			'roles': roles
		}).insert()