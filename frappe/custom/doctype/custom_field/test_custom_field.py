#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
import unittest

test_records = frappe.get_test_records('Custom Field')

class TestCustomField(unittest.TestCase):
	pass
