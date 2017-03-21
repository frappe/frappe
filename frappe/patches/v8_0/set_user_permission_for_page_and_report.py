# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if not frappe.db.exists('DocType', 'Custom Role'):
		frappe.reload_doc("core", 'doctype', "custom_role")
		set_user_permission_for_page_and_report()

	update_ref_doctype_in_custom_role()	

def update_ref_doctype_in_custom_role():
	frappe.reload_doc("core", 'doctype', "custom_role")
	frappe.db.sql("""update `tabCustom Role` 
				set 
					ref_doctype = (select ref_doctype from tabReport where name = `tabCustom Role`.report) 
				where report is not null""")

def set_user_permission_for_page_and_report():
	make_custom_roles_for_page_and_report()

def make_custom_roles_for_page_and_report():
	for doctype in ['Page', 'Report']:
		for data in get_data(doctype):
			doc = frappe.get_doc(doctype, data.name)
			roles = get_roles(doctype, data, doc)
			make_custom_roles(doctype, doc.name, roles)

def get_data(doctype):
	fields = ["name"] if doctype == 'Page' else ["name", "ref_doctype"]
	return frappe.get_all(doctype, fields = fields)

def get_roles(doctype, data, doc):
	roles = []
	if doctype == 'Page':
		for d in doc.roles:
			if frappe.db.exists('Role', d.role):
				roles.append({'role': d.role})
	else:
		out = frappe.get_all('Custom DocPerm', fields='distinct role', filters=dict(parent = data.ref_doctype))
		for d in out:
			roles.append({'role': d.role})
	return roles

def make_custom_roles(doctype, name, roles):
	field = doctype.lower()

	if roles:
		custom_permission = frappe.get_doc({
			'doctype': 'Custom Role',
			field : name,
			'roles' : roles
		}).insert()
