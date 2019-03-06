from __future__ import unicode_literals

# imports - standard imports
import unittest

# imports - module imports
import frappe

# imports - frappe module imports
from frappe.chat.doctype.chat_profile import chat_profile
from frappe.chat.util import get_user_doc, create_test_user


class TestChatProfile(unittest.TestCase):
	pass
	# def test_create(self):
	# 	with self.assertRaises(frappe.ValidationError):
	# 		chat_profile.create(test_user)

	# 	user = get_user_doc(session.user)
	# 	if not user.chat_profile:
	# 		chat_profile.create(user.name)
	# 		prof = chat_profile.get(user.name)
	# 		self.assertEqual(prof.status, 'Online')
	# 	else:
	# 		with self.assertRaises(frappe.ValidationError):
	# 			chat_profile.create(user.name)

	# def test_get(self):
	# 	user = session.user
	# 	prof = chat_profile.get(user)

	# 	self.assertNotEquals(len(prof), 1)

	# 	prof = chat_profile.get(user, fields = ['status'])
	# 	self.assertEqual(len(prof), 1)
	# 	self.assertEqual(prof.status, 'Online')

	# 	prof = chat_profile.get(user, fields = ['status', 'chat_bg'])
	# 	self.assertEqual(len(prof), 2)

	# def test_update(self):
	# 	user = test_user
	# 	with self.assertRaises(frappe.ValidationError):
	# 		prof = chat_profile.update(user, data = dict(
	# 			status = 'Online'
	# 		))

	# 	user = get_user_doc(session.user)
	# 	prev = chat_profile.get(user.name)

	# 	chat_profile.update(user.name, data = dict(
	# 		status = 'Offline'
	# 	))
	# 	prof = chat_profile.get(user.name)
	# 	self.assertEqual(prof.status, 'Offline')
	# 	# revert
	# 	chat_profile.update(user.name, data = dict(
	# 		status = prev.status
	# 	))