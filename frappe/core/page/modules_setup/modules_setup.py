# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import frappe
from frappe.desk.doctype.desktop_icon.desktop_icon import set_hidden_list, get_desktop_icons
from frappe.utils.user import UserPermissions
from frappe import _

@frappe.whitelist()
def update(hidden_list, user=None):
	"""update modules"""
	if not user:
		frappe.only_for('System Manager')

	set_hidden_list(hidden_list, user)
	frappe.msgprint(frappe._('Updated'), indicator='green', title=_('Success'), alert=True)

def get_context(context):
	context.icons = get_user_icons(frappe.session.user)
	context.user = frappe.session.user

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
		{'icons': icons, 'user': user})

def get_user_icons(user):
	'''Get user icons for module setup page'''
	user_perms = UserPermissions(user)
	user_perms.build_permissions()

	from frappe.boot import get_allowed_pages

	allowed_pages = get_allowed_pages()

	icons = []
	for icon in get_desktop_icons(user):
		add = True
		if icon.hidden_in_standard:
			add = False

		if not icon.custom:
			if icon.module_name=='Learn':
				pass

			elif icon.type=="page" and icon.link not in allowed_pages:
				add = False

			elif icon.type=="module" and icon.module_name not in user_perms.allow_modules:
				add = False

		if add:
			icons.append(icon)

	return icons
