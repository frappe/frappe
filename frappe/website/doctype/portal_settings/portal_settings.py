# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies and contributors
# For license information, please see license.txt

from __future__ import unicode_literals
import frappe
from frappe import _
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

def check_portal_enabled(reference_doctype):
	if not frappe.db.get_value('Portal Menu Item',
		{'reference_doctype': reference_doctype}, 'enabled'):
		frappe.throw(_("Request for Quotation is disabled to access from portal, for more check portal settings."))