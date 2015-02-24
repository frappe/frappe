# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('Page')

class TestPage(unittest.TestCase):
	pass
