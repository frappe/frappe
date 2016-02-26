# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import set_hidden, get_desktop_icons
from frappe.utils.user import UserPermissions

@frappe.whitelist()
def update(hidden_list, user=None):
	"""update modules"""
	if not user:
		frappe.only_for('System Manager')

	set_hidden(hidden_list, user)
	frappe.msgprint(frappe._('Updated'))

def get_context(context):
	context.icons = get_user_icons(frappe.session.user)

	if 'System Manager' in frappe.get_roles():
		context.users = frappe.db.get_all('User', filters={'user_type': 'System User', 'enabled': 1},
			fields = ['name', 'first_name', 'last_name'])

@frappe.whitelist()
def get_module_icons_html(user=None):
	if user != frappe.session.user:
		frappe.only_for('System Manager')

	if not user:
		icons = frappe.db.get_all('Desktop Icon',
			fields='*', filters={'standard': 1}, order_by='idx')
	else:
		frappe.cache().hdel('desktop_icons', user)
		icons = get_user_icons(user)

	return frappe.render_template('frappe/core/page/modules_setup/includes/module_icons.html',
		{'icons': icons})

def get_user_icons(user):
	'''Get user icons for module setup page'''
	user_perms = UserPermissions(user)
	user_perms.build_permissions()

	icons = []
	for icon in get_desktop_icons(user):
		print icon.module_name
		if icon.hidden_in_standard:
			continue
		if not icon.custom and not icon.module_name in user_perms.allow_modules:
			continue

		icons.append(icon)

	return icons


