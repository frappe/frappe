# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import getpass

def before_install():
	frappe.reload_doc("core", "doctype", "docfield")
	frappe.reload_doc("core", "doctype", "docperm")
	frappe.reload_doc("core", "doctype", "doctype")

def after_install():
	# reset installed apps for re-install
	frappe.db.set_global("installed_apps", '["frappe"]')

	# core users / roles
	install_docs = [
		{'doctype':'User', 'name':'Administrator', 'first_name':'Administrator',
			'email':'admin@example.com', 'enabled':1},
		{'doctype':'User', 'name':'Guest', 'first_name':'Guest',
			'email':'guest@example.com', 'enabled':1},
		{'doctype':'UserRole', 'parent': 'Administrator', 'role': 'Administrator',
			'parenttype':'User', 'parentfield':'user_roles'},
		{'doctype':'UserRole', 'parent': 'Guest', 'role': 'Guest',
			'parenttype':'User', 'parentfield':'user_roles'},
		{'doctype': "Role", "role_name": "Report Manager"},
		{'doctype': "Workflow State", "workflow_state_name": "Pending",
			"icon": "question-sign", "style": ""},
		{'doctype': "Workflow State", "workflow_state_name": "Approved",
			"icon": "ok-sign", "style": "Success"},
		{'doctype': "Workflow State", "workflow_state_name": "Rejected",
			"icon": "remove", "style": "Danger"},
		{'doctype': "Workflow Action", "workflow_action_name": "Approve"},
		{'doctype': "Workflow Action", "workflow_action_name": "Reject"},
		{'doctype': "Workflow Action", "workflow_action_name": "Review"}
	]

	for d in install_docs:
		try:
			frappe.get_doc(d).insert()
		except frappe.NameError:
			pass

	# all roles to admin
	frappe.get_doc("User", "Administrator").add_roles(*frappe.db.sql_list("""select name from tabRole"""))

	# update admin password
	from frappe.auth import _update_password
	_update_password("Administrator", get_admin_password())

	frappe.db.commit()

def get_admin_password():
	def ask_admin_password():
		admin_password = getpass.getpass("Set Administrator password: ")
		admin_password2 = getpass.getpass("Re-enter Administrator password: ")
		if not admin_password == admin_password2:
			print "\nPasswords do not match"
			return ask_admin_password()
		return admin_password

	admin_password = frappe.conf.get("admin_password")
	if not admin_password:
		return ask_admin_password()
	return admin_password


def before_tests():
	frappe.db.sql("delete from `tabCustom Field`")
	frappe.db.sql("delete from `tabEvent`")
	frappe.db.commit()
	frappe.clear_cache()
