# imports - standard imports
import unittest

# imports - module imports
from frappe.chat.util import (
	get_user_doc,
	safe_json_loads
)
import frappe

class TestChatUtil(unittest.TestCase):
	def test_safe_json_loads(self):
		number = safe_json_loads("1")
		self.assertEquals(type(number), int)

		number = safe_json_loads("1.0")
		self.assertEquals(type(number), float)
		
		string = safe_json_loads("foobar")
		self.assertEquals(type(string), str)
		
		array  = safe_json_loads('[{ "foo": "bar" }]')
		self.assertEquals(type(array), list)

		objekt = safe_json_loads('{ "foo": "bar" }')
		self.assertEquals(type(objekt), dict)

		true, null = safe_json_loads("true", "null")
		self.assertEquals(true, True)
		self.assertEquals(null, None)

	def test_get_user_doc(self):
		# Needs more test cases.
		user = get_user_doc()
		self.assertEquals(user.name, frappe.session.user)