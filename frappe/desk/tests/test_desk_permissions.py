# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest
import frappe
from frappe.desk.permissions import *

class TestDeskPermissions(unittest.TestCase):
	def test_get_permissions(self):
		perms = get_permissions()
		print(perms)
