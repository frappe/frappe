# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

"""Use blog post test to test user permissions logic"""

import frappe
import frappe.defaults
import unittest
import json

from frappe.desk.doctype.event.event import get_events
from frappe.test_runner import make_test_objects

test_records = frappe.get_test_records('Event')

class TestEvent(unittest.TestCase):
	def setUp(self):
		frappe.db.sql('delete from tabEvent')
		make_test_objects('Event', reset=True)

		self.test_records = frappe.get_test_records('Event')
		self.test_user = "test1@example.com"

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_allowed_public(self):
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject":"_Test Event 1"}))
		self.assertTrue(frappe.has_permission("Event", doc=doc))

	def test_not_allowed_private(self):
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject":"_Test Event 2"}))
		self.assertFalse(frappe.has_permission("Event", doc=doc))

	def test_allowed_private_if_in_event_user(self):
		name = frappe.db.get_value("Event", {"subject":"_Test Event 3"})
		frappe.share.add("Event", name, self.test_user, "read")
		frappe.set_user(self.test_user)
		doc = frappe.get_doc("Event", name)
		self.assertTrue(frappe.has_permission("Event", doc=doc))
		frappe.set_user("Administrator")
		frappe.share.remove("Event", name, self.test_user)

	def test_event_list(self):
		frappe.set_user(self.test_user)
		res = frappe.get_list("Event", filters=[["Event", "subject", "like", "_Test Event%"]], fields=["name", "subject"])
		self.assertEqual(len(res), 1)
		subjects = [r.subject for r in res]
		self.assertTrue("_Test Event 1" in subjects)
		self.assertFalse("_Test Event 3" in subjects)
		self.assertFalse("_Test Event 2" in subjects)

	def test_revert_logic(self):
		ev = frappe.get_doc(self.test_records[0]).insert()
		name = ev.name

		frappe.delete_doc("Event", ev.name)

		# insert again
		ev = frappe.get_doc(self.test_records[0]).insert()

		# the name should be same!
		self.assertEqual(ev.name, name)

	def test_assign(self):
		from frappe.desk.form.assign_to import add

		ev = frappe.get_doc(self.test_records[0]).insert()

		add({
			"assign_to": ["test@example.com"],
			"doctype": "Event",
			"name": ev.name,
			"description": "Test Assignment"
		})

		ev = frappe.get_doc("Event", ev.name)

		self.assertEqual(ev._assign, json.dumps(["test@example.com"]))

		# add another one
		add({
			"assign_to": [self.test_user],
			"doctype": "Event",
			"name": ev.name,
			"description": "Test Assignment"
		})

		ev = frappe.get_doc("Event", ev.name)

		self.assertEqual(set(json.loads(ev._assign)), set(["test@example.com", self.test_user]))

		# Remove an assignment
		todo = frappe.get_doc("ToDo", {"reference_type": ev.doctype, "reference_name": ev.name,
			"owner": self.test_user})
		todo.status = "Cancelled"
		todo.save()

		ev = frappe.get_doc("Event", ev.name)
		self.assertEqual(ev._assign, json.dumps(["test@example.com"]))

		# cleanup
		ev.delete()

	def test_recurring(self):
		ev = frappe.get_doc({
			"doctype":"Event",
			"subject": "_Test Event",
			"starts_on": "2014-02-01",
			"event_type": "Public",
			"repeat_this_event": 1,
			"repeat_on": "Yearly"
		})
		ev.insert()

		ev_list = get_events("2014-02-01", "2014-02-01", "Administrator", for_reminder=True)
		self.assertTrue(bool(list(filter(lambda e: e.name==ev.name, ev_list))))

		ev_list1 = get_events("2015-01-20", "2015-01-20", "Administrator", for_reminder=True)
		self.assertFalse(bool(list(filter(lambda e: e.name==ev.name, ev_list1))))

		ev_list2 = get_events("2014-02-20", "2014-02-20", "Administrator", for_reminder=True)
		self.assertFalse(bool(list(filter(lambda e: e.name==ev.name, ev_list2))))

		ev_list3 = get_events("2015-02-01", "2015-02-01", "Administrator", for_reminder=True)
		self.assertTrue(bool(list(filter(lambda e: e.name==ev.name, ev_list3))))
