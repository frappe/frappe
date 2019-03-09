from __future__ import unicode_literals

# imports - standard imports
import unittest

# imports - module imports
import frappe

# imports - frappe module imports
from frappe.chat.doctype.chat_message import chat_message
from frappe.chat.util import create_test_user


class TestChatMessage(unittest.TestCase):
	def test_send(self):
		# TODO - Write the case once you're done with Chat Room
		# user = test_user
		# chat_message.send(user, room, 'foobar')
		pass
