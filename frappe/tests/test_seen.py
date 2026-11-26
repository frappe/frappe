# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import get_user_by_email


class TestSeen(IntegrationTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_if_user_is_added(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test event for seen",
				"starts_on": "2016-01-01 10:10:00",
				"event_type": "Public",
			}
		).insert()
		user = get_user_by_email("test@example.com")
		user1 = get_user_by_email("test1@example.com")

		frappe.set_user("test@example.com")

		from frappe.desk.form.load import getdoc

		# load the form
		getdoc("Event", ev.name)

		# reload the event
		ev = frappe.get_doc("Event", ev.name)

		self.assertTrue(user in json.loads(ev._seen))

		# test another user
		frappe.set_user("test1@example.com")

		# load the form
		getdoc("Event", ev.name)

		# reload the event
		ev = frappe.get_doc("Event", ev.name)

		self.assertTrue(user in json.loads(ev._seen))
		self.assertTrue(user1 in json.loads(ev._seen))

		ev.save(ignore_permissions=True)
		ev = frappe.get_doc("Event", ev.name)

		self.assertFalse(user in json.loads(ev._seen))
		self.assertTrue(user1 in json.loads(ev._seen))
