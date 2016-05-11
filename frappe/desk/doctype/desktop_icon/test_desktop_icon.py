# -*- coding: utf-8 -*-
# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

from frappe.desk.doctype.desktop_icon.desktop_icon import (get_desktop_icons, add_user_icon,
	set_hidden_list, set_order, clear_desktop_icons_cache)

# test_records = frappe.get_test_records('Desktop Icon')

class TestDesktopIcon(unittest.TestCase):
	def setUp(self):
		frappe.set_user('test@example.com')
		frappe.db.sql('delete from `tabDesktop Icon` where standard=0')
		frappe.db.sql('delete from `tabBlock Module`')
		frappe.db.sql('update `tabDesktop Icon` set hidden=0, blocked=0')

	def tearDown(self):
		frappe.set_user('Administrator')

	def get_icon(self, module_name):
		for i in get_desktop_icons():
			if i.module_name == module_name:
				return i

		return None

	def test_get_standard_desktop_icon_for_user(self):
		self.assertEquals(self.get_icon('Desk').standard, 1)

	def test_add_desktop_icon(self):
		self.assertEquals(self.get_icon('User'), None)
		add_user_icon('User')

		icon = self.get_icon('User')
		self.assertEquals(icon.custom, 1)
		self.assertEquals(icon.standard, 0)

	def test_hide_desktop_icon(self):
		set_hidden_list(["Desk"], 'test@example.com')

		icon = self.get_icon('Desk')
		self.assertEquals(icon.hidden, 1)
		self.assertEquals(icon.standard, 0)

	def test_remove_custom_desktop_icon_on_hidden(self):
		self.test_add_desktop_icon()
		set_hidden_list(['User'], 'test@example.com')

		icon = self.get_icon('User')
		self.assertEquals(icon, None)

	def test_show_desktop_icon(self):
		self.test_hide_desktop_icon()
		set_hidden_list([], 'test@example.com')

		icon = self.get_icon('Desk')
		self.assertEquals(icon.hidden, 0)
		self.assertEquals(icon.standard, 0)

	def test_globally_hidden_desktop_icon(self):
		set_hidden_list(["Desk"])

		icon = self.get_icon('Desk')
		self.assertEquals(icon.hidden, 1)

		frappe.set_user('test1@example.com')
		icon = self.get_icon('Desk')
		self.assertEquals(icon.hidden, 1)

	def test_re_order_desktop_icons(self):
		icons = [d.module_name for d in get_desktop_icons()]
		m0, m1 = icons[0], icons[1]
		set_order([m1, m0] + icons[2:], frappe.session.user)

		# reload
		icons = [d.module_name for d in get_desktop_icons()]

		# check switched order
		self.assertEquals(icons[0], m1)
		self.assertEquals(icons[1], m0)

	def test_block_desktop_icons_for_user(self):
		def test_unblock():
			user = frappe.get_doc('User', 'test@example.com')
			user.block_modules = []
			user.save(ignore_permissions = 1)

			icon = self.get_icon('Desk')
			self.assertEquals(icon.hidden, 0)

		test_unblock()

		user = frappe.get_doc('User', 'test@example.com')
		user.append('block_modules', {'module': 'Desk'})
		user.save(ignore_permissions = 1)
		clear_desktop_icons_cache(user.name)

		icon = self.get_icon('Desk')
		self.assertEquals(icon.hidden, 1)

		test_unblock()


