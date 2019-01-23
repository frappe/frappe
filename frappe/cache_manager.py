# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals

import frappe
import frappe.defaults
from frappe.desk.notifications import (delete_notification_count_for,
	clear_notifications)

common_default_keys = ["__default", "__global"]

def clear_user_cache(user=None):
	cache = frappe.cache()

	groups = ("bootinfo", "user_recent", "roles", "user_doc", "lang",
		"defaults", "user_permissions", "home_page", "linked_with",
		"desktop_icons", 'portal_menu_items')

	# this will automatically reload the global cache
	# so it is important to clear this first
	clear_notifications(user)

	if user:
		for name in groups:
			cache.hdel(name, user)
		cache.delete_keys("user:" + user)
		clear_defaults_cache(user)
	else:
		for name in groups:
			cache.delete_key(name)
		clear_defaults_cache()
		clear_global_cache()

def clear_global_cache():
	from frappe.website.render import clear_cache as clear_website_cache

	clear_doctype_cache()
	clear_website_cache()
	frappe.cache().delete_value(["app_hooks", "installed_apps",
		"app_modules", "module_app", "notification_config", 'system_settings',
		'scheduler_events', 'time_zone', 'webhooks', 'active_domains', 'active_modules'])
	frappe.setup_module_map()

def clear_defaults_cache(user=None):
	if user:
		for p in ([user] + common_default_keys):
			frappe.cache().hdel("defaults", p)
	elif frappe.flags.in_install!="frappe":
		frappe.cache().delete_key("defaults")

def clear_document_cache():
	frappe.local.document_cache = {}
	frappe.cache().delete_key("document_cache")

def clear_doctype_cache(doctype=None):
	cache = frappe.cache()

	if getattr(frappe.local, 'meta_cache') and (doctype in frappe.local.meta_cache):
		del frappe.local.meta_cache[doctype]

	for key in ('is_table', 'doctype_modules'):
		cache.delete_value(key)

	groups = ["meta", "form_meta", "table_columns", "last_modified",
		"linked_doctypes", 'notifications', 'workflow']

	def clear_single(dt):
		for name in groups:
			cache.hdel(name, dt)

	if doctype:
		clear_single(doctype)

		# clear all parent doctypes

		for dt in frappe.db.get_all('DocField', 'parent',
			dict(fieldtype=['in', frappe.model.table_fields], options=doctype)):
			clear_single(dt.parent)

		# clear all notifications
		delete_notification_count_for(doctype)

	else:
		# clear all
		for name in groups:
			cache.delete_value(name)

	# Clear all document's cache. To clear documents of a specific DocType document_cache should be restructured
	clear_document_cache()

