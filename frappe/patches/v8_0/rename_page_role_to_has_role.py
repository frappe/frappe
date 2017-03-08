# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
	if not frappe.db.exists('DocType', 'Has Role'):
		frappe.rename_doc('DocType', 'Page Role', 'Has Role')
		reload_doc()
		set_ref_doctype_roles_to_report()
		copy_user_roles_to_has_roles()
		set_user_permission_for_page_and_report()
		remove_doctypes()

def reload_doc():
	frappe.reload_doc("core", 'doctype', "page")
	frappe.reload_doc("core", 'doctype', "report")
	frappe.reload_doc("core", 'doctype', "user")
	frappe.reload_doc("core", 'doctype', "has_role")
	frappe.reload_doc("core", 'doctype', "custom_role")
	
def set_ref_doctype_roles_to_report():
	for data in frappe.get_all('Report', fields=["name"]):
		doc = frappe.get_doc('Report', data.name)
		if frappe.db.exists("DocType", doc.ref_doctype):
			try:
				doc.set_doctype_roles()
				for row in doc.roles:
					row.db_update()
			except:
				pass
				
def copy_user_roles_to_has_roles():
	for data in frappe.get_all('User', fields = ["name"]):
		doc = frappe.get_doc('User', data.name)
		doc.set('roles',[])
		for args in frappe.get_all('UserRole', fields = ["role"], 
			filters = {'parent': data.name, 'parenttype': 'User'}):
			doc.append('roles', {
				'role': args.role
			})
		for role in doc.roles:
			role.db_update()
			
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
		if not out:
			out = frappe.get_all('DocPerm', fields='distinct role', filters=dict(parent = data.ref_doctype))
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

def remove_doctypes():
	for doctype in ['UserRole', 'Event Role']:
		if frappe.db.exists('DocType', doctype):
			frappe.delete_doc('DocType', doctype)
