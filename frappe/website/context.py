# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
import json
import os

import frappe
from frappe.model.document import Document

def get_sidebar_data(parent_sidebar, basepath):
	import frappe.www.list
	sidebar_data = frappe._dict()

	hooks = frappe.get_hooks('look_for_sidebar_json')
	look_for_sidebar_json = hooks[0] if hooks else 0

	if basepath and look_for_sidebar_json:
		sidebar_items = get_sidebar_items_from_sidebar_file(basepath, look_for_sidebar_json)
		sidebar_data['sidebar_items'] = sidebar_items

	if not sidebar_data.sidebar_items and parent_sidebar:
		sidebar_data.sidebar_items = frappe.get_all('Website Sidebar Item',
			filters=dict(parent=parent_sidebar), fields=['title', 'route', '`group`'],
			order_by='idx asc')

	if not sidebar_data.sidebar_items:
		sidebar_items = frappe.cache().hget('portal_menu_items', frappe.session.user)
		if sidebar_items == None:
			sidebar_items = []
			roles = frappe.get_roles()
			portal_settings = frappe.get_doc('Portal Settings', 'Portal Settings')

			def add_items(sidebar_items, items):
				for d in items:
					if d.get('enabled') and ((not d.get('role')) or d.get('role') in roles):
						sidebar_items.append(d.as_dict() if isinstance(d, Document) else d)

			if not portal_settings.hide_standard_menu:
				add_items(sidebar_items, portal_settings.get('menu'))

			if portal_settings.custom_menu:
				add_items(sidebar_items, portal_settings.get('custom_menu'))

			items_via_hooks = frappe.get_hooks('portal_menu_items')
			if items_via_hooks:
				for i in items_via_hooks: i['enabled'] = 1
				add_items(sidebar_items, items_via_hooks)

			frappe.cache().hset('portal_menu_items', frappe.session.user, sidebar_items)
		sidebar_data.sidebar_items = sidebar_items

	return sidebar_data

def get_sidebar_items_from_sidebar_file(basepath, look_for_sidebar_json):
	sidebar_items = frappe._dict()
	sidebar_json_path = get_sidebar_json_path(basepath, look_for_sidebar_json)
	if not sidebar_json_path: return sidebar_items

	with open(sidebar_json_path, 'r') as sidebarfile:
		try:
			sidebar_json = sidebarfile.read()
			sidebar_items = json.loads(sidebar_json)
		except json.decoder.JSONDecodeError:
			frappe.throw('Invalid Sidebar JSON at ' + sidebar_json_path)

	return sidebar_items

def get_sidebar_json_path(path, look_for=False):
	'''
		Get _sidebar.json path from directory path

		:param path: path of the current diretory
		:param look_for: if True, look for _sidebar.json going upwards from given path

		:return: _sidebar.json path
	'''
	if os.path.split(path)[1] == 'www' or path == '/' or not path:
		return ''

	sidebar_json_path = os.path.join(path, '_sidebar.json')
	if os.path.exists(sidebar_json_path):
		return sidebar_json_path
	else:
		if look_for:
			return get_sidebar_json_path(os.path.split(path)[0], look_for)
		else:
			return ''
