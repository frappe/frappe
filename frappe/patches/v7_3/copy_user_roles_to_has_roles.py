# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# License: GNU General Public License v3. See license.txt

from __future__ import unicode_literals
import frappe

def execute():
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