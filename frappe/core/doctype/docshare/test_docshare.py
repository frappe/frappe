# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# See license.txt

import frappe
import frappe.share
import unittest

class TestDocShare(unittest.TestCase):
	def setUp(self):
		self.user = "test@example.com"
		self.event = frappe.get_doc({"doctype": "Event",
			"subject": "test share event",
			"starts_on": "2015-01-01 10:00:00",
			"event_type": "Private"}).insert()

	def tearDown(self):
		frappe.set_user("Administrator")
		self.event.delete()

	def test_add(self):
		# user not shared
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", self.user))
		frappe.share.add("Event", self.event.name, self.user)
		self.assertTrue(self.event.name in frappe.share.get_shared("Event", self.user))

	def test_doc_permission(self):
		frappe.set_user(self.user)
		self.assertFalse(self.event.has_permission())

		frappe.set_user("Administrator")
		frappe.share.add("Event", self.event.name, self.user)

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission())

	def test_share_permission(self):
		frappe.share.add("Event", self.event.name, self.user, write=1, share=1)

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

		# test cascade
		self.assertTrue(self.event.has_permission("read"))
		self.assertTrue(self.event.has_permission("write"))

	def test_set_permission(self):
		frappe.share.add("Event", self.event.name, self.user)

		frappe.set_user(self.user)
		self.assertFalse(self.event.has_permission("share"))

		frappe.set_user("Administrator")
		frappe.share.set_permission("Event", self.event.name, self.user, "share")

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

	def test_permission_to_share(self):
		frappe.set_user(self.user)
		self.assertRaises(frappe.PermissionError, frappe.share.add, "Event", self.event.name, self.user)

		frappe.set_user("Administrator")
		frappe.share.add("Event", self.event.name, self.user, write=1, share=1)

		# test not raises
		frappe.set_user(self.user)
		frappe.share.add("Event", self.event.name, "test1@example.com", write=1, share=1)

	def test_remove_share(self):
		frappe.share.add("Event", self.event.name, self.user, write=1, share=1)

		frappe.set_user(self.user)
		self.assertTrue(self.event.has_permission("share"))

		frappe.set_user("Administrator")
		frappe.share.remove("Event", self.event.name, self.user)

		frappe.set_user(self.user)
		self.assertFalse(self.event.has_permission("share"))

	def test_share_with_everyone(self):
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", self.user))

		frappe.share.set_permission("Event", self.event.name, None, "read", everyone=1)
		self.assertTrue(self.event.name in frappe.share.get_shared("Event", self.user))
		self.assertTrue(self.event.name in frappe.share.get_shared("Event", "test1@example.com"))
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", "Guest"))

		frappe.share.set_permission("Event", self.event.name, None, "read", value=0, everyone=1)
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", self.user))
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", "test1@example.com"))
		self.assertTrue(self.event.name not in frappe.share.get_shared("Event", "Guest"))
