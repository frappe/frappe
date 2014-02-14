# Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

"""Use blog post test to test permission restriction logic"""

test_records = [
	[{
		"doctype": "Event",
		"subject":"_Test Event 1",
		"starts_on": "2014-01-01",
		"event_type": "Public",
	}],
	[{
		"doctype": "Event",
		"starts_on": "2014-01-01",
		"subject":"_Test Event 2",
		"event_type": "Private",
	}],
	[{
		"doctype": "Event",
		"starts_on": "2014-01-01",
		"subject":"_Test Event 3",
		"event_type": "Private",
	}, {
		"doctype": "Event User",
		"parentfield": "event_individuals",
		"person": "test1@example.com"
	}],
	
]

import frappe
import frappe.defaults
import unittest

class TestEvent(unittest.TestCase):
	# def setUp(self):
	# 	profile = frappe.bean("Profile", "test1@example.com")
	# 	profile.get_controller().add_roles("Website Manager")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_allowed_public(self):
		frappe.set_user("test1@example.com")
		doc = frappe.doc("Event", frappe.conn.get_value("Event", {"subject":"_Test Event 1"}))
		self.assertTrue(frappe.has_permission("Event", refdoc=doc))
				
	def test_not_allowed_private(self):
		frappe.set_user("test1@example.com")
		doc = frappe.doc("Event", frappe.conn.get_value("Event", {"subject":"_Test Event 2"}))
		self.assertFalse(frappe.has_permission("Event", refdoc=doc))

	def test_allowed_private_if_in_event_user(self):
		frappe.set_user("test1@example.com")
		doc = frappe.doc("Event", frappe.conn.get_value("Event", {"subject":"_Test Event 3"}))
		self.assertTrue(frappe.has_permission("Event", refdoc=doc))
		
	def test_event_list(self):
		frappe.set_user("test1@example.com")
		res = frappe.get_list("Event", filters=[["Event", "subject", "like", "_Test Event%"]], fields=["name", "subject"])
		self.assertEquals(len(res), 2)
		subjects = [r.subject for r in res]
		self.assertTrue("_Test Event 1" in subjects)
		self.assertTrue("_Test Event 3" in subjects)
		self.assertFalse("_Test Event 2" in subjects)
	