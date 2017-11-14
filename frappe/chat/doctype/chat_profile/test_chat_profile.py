# imports - standard imports
import unittest

# imports - module imports
import frappe
from   frappe.exceptions import DuplicateEntryError

# imports - frappe module imports
from frappe.chat.doctype.chat_profile import chat_profile
from frappe.chat.util import get_user_doc

session = frappe.session

try:
	test_user = frappe.new_doc('User')
	test_user.first_name = 'Test User Chat Profile'
	test_user.email      = 'testuser.chatprofile@example.com'
	test_user.save()
except DuplicateEntryError:
	frappe.log('Test User Chat Profile exists.')

class TestChatProfile(unittest.TestCase):
	def test_create(self):
		with self.assertRaises(frappe.ValidationError):
			chat_profile.create(test_user)
		
		user = get_user_doc(session.user)
		if not user.chat_profile:
			chat_profile.create(user.name)
			prof = chat_profile.get(user.name)
			self.assertEquals(prof.status, 'Online')
		else:
			with self.assertRaises(frappe.ValidationError):
				chat_profile.create(user.name)

	def test_get(self):
		user = session.user
		prof = chat_profile.get(user)

		self.assertNotEquals(len(prof), 1)

		prof = chat_profile.get(user, fields = ['status'])
		self.assertEquals(len(prof), 1)
		self.assertEquals(prof.status, 'Online')

		prof = chat_profile.get(user, fields = ['status', 'chat_bg'])
		self.assertEquals(len(prof), 2)

	def test_update(self):
		user = test_user
		with self.assertRaises(frappe.ValidationError):
			prof = chat_profile.update(user, data = dict(
				status = 'Online'
			))

		user = get_user_doc(session.user)
		chat_profile.update(user.name, data = dict(
			status = 'Offline'
		))
		prof = chat_profile.get(user.name)
		self.assertEquals(prof.status, 'Offline')
		# revert
		chat_profile.update(user.name, data = dict(
			status = 'Online'
		))