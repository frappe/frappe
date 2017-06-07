# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt
from __future__ import unicode_literals

import frappe
import unittest
test_records = frappe.get_test_records('Communication')


class TestCommunication(unittest.TestCase):

	def test_email(self):
		valid_email_list = ["Full Name <full@example.com>",
		'"Full Name with quotes and <weird@chars.com>" <weird@example.com>',
		"Surname, Name <name.surname@domain.com>",
		"Purchase@ABC <purchase@abc.com>", "xyz@abc2.com <xyz@abc.com>",
		"Name [something else] <name@domain.com>"]

		invalid_email_list = ["[invalid!email]", "invalid-email",
		"tes2", "e", "rrrrrrrr", "manas","[[[sample]]]",
		"[invalid!email].com"]

		for x in valid_email_list:
			self.assertTrue(frappe.utils.parse_addr(x)[1])

		for x in invalid_email_list:
			self.assertFalse(frappe.utils.parse_addr(x)[0])

	def test_name(self):
		valid_email_list = ["Full Name <full@example.com>",
		'"Full Name with quotes and <weird@chars.com>" <weird@example.com>',
		"Surname, Name <name.surname@domain.com>",
		"Purchase@ABC <purchase@abc.com>", "xyz@abc2.com <xyz@abc.com>",
		"Name [something else] <name@domain.com>"]

		invalid_email_list = ["[invalid!email]", "invalid-email",
		"tes2", "e", "rrrrrrrr", "manas","[[[sample]]]",
		"[invalid!email].com"]

		for x in valid_email_list:
			self.assertTrue(frappe.utils.parse_addr(x)[0])

		for x in invalid_email_list:
			self.assertFalse(frappe.utils.parse_addr(x)[0])

