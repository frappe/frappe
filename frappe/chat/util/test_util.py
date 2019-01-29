from __future__ import unicode_literals

# imports - standard imports
import unittest

# imports - module imports
from frappe.chat.util import (
	get_user_doc,
	safe_json_loads
)
import frappe
import six

class TestChatUtil(unittest.TestCase):
	def test_safe_json_loads(self):
		number = safe_json_loads("1")
		self.assertEqual(type(number), int)

		number = safe_json_loads("1.0")
		self.assertEqual(type(number), float)

		string = safe_json_loads("foobar")
		self.assertEqual(type(string), six.text_type)

		array  = safe_json_loads('[{ "foo": "bar" }]')
		self.assertEqual(type(array), list)

		objekt = safe_json_loads('{ "foo": "bar" }')
		self.assertEqual(type(objekt), dict)

		true, null = safe_json_loads("true", "null")
		self.assertEqual(true, True)
		self.assertEqual(null, None)

	def test_get_user_doc(self):
		# Needs more test cases.
		user = get_user_doc()
		self.assertEqual(user.name, frappe.session.user)