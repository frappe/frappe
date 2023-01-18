# -*- coding: utf-8 -*-
# Copyright (c) 2020, Frappe Technologies and Contributors
<<<<<<< HEAD
# See license.txt
from __future__ import unicode_literals

# import frappe
import unittest


class TestInstalledApplications(unittest.TestCase):
	pass
=======
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.installed_applications.installed_applications import (
	InvalidAppOrder,
	update_installed_apps_order,
)
from frappe.tests.utils import FrappeTestCase


class TestInstalledApplications(FrappeTestCase):
	def test_order_change(self):
		update_installed_apps_order(["frappe"])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, [])
		self.assertRaises(InvalidAppOrder, update_installed_apps_order, ["frappe", "deepmind"])
>>>>>>> 1796cae6bf (feat: let users modify hook resolution order)
