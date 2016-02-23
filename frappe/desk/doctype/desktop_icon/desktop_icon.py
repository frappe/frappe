# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and contributors
# For license information, please see license.txt

from __future__ import unicode_literals

import frappe
import json
from frappe.model.document import Document

class DesktopIcon(Document):
	def validate(self):
		if not self.label:
			self.label = self.module_name

def get_desktop_icons(user=None):
	'''Return desktop icons for user'''
	if not user:
		user = frappe.session.user

	user_icons = frappe.cache().hget('desktop_icons', user)

	if not user_icons:
		fields = ['module_name', 'hidden', 'label', 'link', 'type', 'icon', 'color',
			'_doctype', 'idx', 'force_show', 'reverse']

		standard_icons = frappe.db.get_all('Desktop Icon',
			fields=fields, filters={'standard': 1})

		standard_map = {}
		for icon in standard_icons:
			standard_map[icon.module_name] = icon

		user_icons = frappe.db.get_all('Desktop Icon', fields=fields,
			filters={'standard': 0, 'owner': user})

		user_blocked_modules = frappe.get_doc('User', user).get_blocked_modules()

		# update hidden property
		for icon in user_icons:
			standard_icon = standard_map[icon.module_name]

			# override properties from standard icon
			for key in ('hidden', 'route', 'label', 'color', 'icon'):
				if standard_icon.get(key):
					icon[key] = standard_icon.get(key)

			if icon.module_name in user_blocked_modules:
				icon.hidden = 1

			if standard_icon.force_show:
				icon.hidden = 0

		# add missing standard icons (added via new install apps?)
		user_icon_names = [icon.module_name for icon in user_icons]
		for standard_icon in standard_icons:
			if standard_icon.module_name not in user_icon_names:
				user_icons.append(standard_icon)

		# sort by idx
		user_icons.sort(lambda a, b: 1 if a.idx > b.idx else -1)

		frappe.cache().hset('desktop_icons', user, user_icons)

	return user_icons

def after_doctype_insert():
	frappe.db.add_unique('Desktop Icon', ('module_name', 'owner', 'standard'))

@frappe.whitelist()
def set_order(new_order):
	'''set new order by duplicating user icons'''
	new_order = json.loads(new_order)
	for i, module_name in enumerate(new_order):
		icon = get_user_copy(module_name, frappe.session.user)
		icon.db_set('idx', i)

	clear_desktop_icons_cache()

def clear_desktop_icons_cache():
	frappe.cache().hdel('desktop_icons', frappe.session.user)
	frappe.cache().hdel('bootinfo', frappe.session.user)

def get_user_copy(module_name, app=None, user=None):
	'''Return user copy (Desktop Icon) of the given module_name. If user copy does not exist, create one.

	:param module_name: Name of the module
	:param user: User for which the copy is required (optional)
	'''
	if not user:
		user = frappe.session.user

	original_name = frappe.db.get_value('Desktop Icon', {'module_name': module_name, 'standard': 1})

	if not original_name:
		frappe.throw('{0} not found'.format(module_name))

	original = frappe.get_doc('Desktop Icon', original_name)

	existing_copy = frappe.db.get_value('Desktop Icon',
		{'module_name': module_name, 'owner': user, 'standard': 0})

	if existing_copy:
		desktop_icon = frappe.get_doc('Desktop Icon', existing_copy)
	else:
		desktop_icon = frappe.get_doc({
			'doctype': 'Desktop Icon',
			'standard': 0,
			'owner': user,
			'module_name': module_name
		})

		for key in ('app', 'label', 'route', 'type', '_doctype', 'idx', 'reverse', 'force_show'):
			if original.get(key):
				desktop_icon.set(key, original.get(key))

		desktop_icon.insert()

	return desktop_icon

def sync_from_app(app):
	'''Sync desktop icons from app. To be called during install'''
	try:
		modules = frappe.get_attr(app + '.config.desktop.get_data')() or {}
	except ImportError:
		return []

	if isinstance(modules, dict):
		modules_list = []
		for m, desktop_icon in modules.iteritems():
			desktop_icon['module_name'] = m
			modules_list.append(desktop_icon)
	else:
		modules_list = modules

	for i, m in enumerate(modules_list):
		desktop_icon_name = frappe.db.get_value('Desktop Icon',
			{'module_name': m['module_name'], 'app': app, 'standard': 1})
		if desktop_icon_name:
			desktop_icon = frappe.get_doc('Desktop Icon', desktop_icon_name)
		else:
			# new icon
			desktop_icon = frappe.get_doc({
				'doctype': 'Desktop Icon',
				'idx': i,
				'standard': 1,
				'app': app,
				'owner': 'Administrator'
			})

		if 'doctype' in m:
			m['_doctype'] = m.pop('doctype')

		desktop_icon.update(m)
		desktop_icon.save()

	return modules_list

