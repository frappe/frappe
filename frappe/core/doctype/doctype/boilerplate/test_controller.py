# Copyright (c) 2013, {app_publisher} and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest

test_records = frappe.get_test_records('{doctype}')

class Test{classname}(unittest.TestCase):
	pass
