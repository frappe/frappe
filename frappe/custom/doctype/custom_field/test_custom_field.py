#  -*- coding: utf-8 -*-

# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Custom Field')

from frappe.model.db_schema import InvalidColumnName

class TestCustomField(unittest.TestCase):
	pass
