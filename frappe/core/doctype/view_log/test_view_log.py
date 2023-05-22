# Copyright (c) 2018, Frappe Technologies and Contributors
# License: MIT. See LICENSE
import frappe
from frappe.tests.utils import FrappeTestCase


class TestViewLog(FrappeTestCase):
	def tearDown(self):
		frappe.set_user("Administrator")

	def test_if_user_is_added(self):
		ev = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test event for view logs",
				"starts_on": "2018-06-04 14:11:00",
				"event_type": "Public",
			}
		).insert()

		frappe.set_user("test@example.com")

		from frappe.desk.form.load import getdoc

		# load the form
		getdoc("Event", ev.name)
		a = frappe.get_value(
			doctype="View Log",
			filters={"reference_doctype": "Event", "reference_name": ev.name},
			fieldname=["viewed_by"],
		)

		self.assertEqual("test@example.com", a)
		self.assertNotEqual("test1@example.com", a)
