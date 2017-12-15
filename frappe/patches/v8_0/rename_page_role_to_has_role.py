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
	remove_doctypes()

def reload_doc():
	frappe.reload_doc("core", 'doctype', "page")
	frappe.reload_doc("core", 'doctype', "report")
	frappe.reload_doc("core", 'doctype', "user")
	frappe.reload_doc("core", 'doctype', "has_role")
	
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
	if frappe.db.exists('DocType', 'UserRole'):
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

def remove_doctypes():
	for doctype in ['UserRole', 'Event Role']:
		if frappe.db.exists('DocType', doctype):
			frappe.delete_doc('DocType', doctype)