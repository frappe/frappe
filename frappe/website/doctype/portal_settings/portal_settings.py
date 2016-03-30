# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe.model.document import Document

class PortalSettings(Document):
	def add_item(self, item):
		'''insert new portal menu item if route is not set'''
		if not item.get('route') in [d.route for d in self.get('menu', [])]:
			item['enabled'] = 1
			self.append('menu', item)
			return True

	def reset(self):
		'''Restore defaults'''
		self.menu = []
		self.sync_menu()

	def sync_menu(self):
		'''Sync portal menu items'''
		dirty = False
		for item in frappe.get_hooks('portal_menu_items'):
			if self.add_item(item):
				dirty = True

		if dirty:
			self.save()

