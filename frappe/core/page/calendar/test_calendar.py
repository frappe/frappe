from __future__ import unicode_literals

import frappe.core.page.calendar.calendar as cal
import frappe
import datetime
import unittest

def create_test_calendar_events():
	frappe.set_user("Administrator")
	doc = frappe.get_list("Event", filters={"Subject": "_Test_Cal Event 1"},fields=["subject","name"])

	if len(doc) != 0:
		return doc
	else:
		doc = frappe.get_doc({
			"doctype": "Event",
			"subject":"_Test_Cal Event 1",
			"starts_on": frappe.utils.nowdate(),
			"ends_on": frappe.utils.add_days(frappe.utils.nowdate(), 3),
			"event_type": "Public",
			"description": "Test_description"
		}).insert()
		return [{
			"name" : doc.name,
			"subject" : doc.subject
		}]

class TestCalendar(unittest.TestCase):

	def test_calendar(self):
		doc = create_test_calendar_events()
		start = datetime.datetime.now()
		end = datetime.datetime.now() + datetime.timedelta(days= 3)

		events = cal.get_master_calendar_events('["Event"]',start.strftime("%Y-%m-%d 00:00:00"),end.strftime("%Y-%m-%d 00:00:00"))

		self.assertEquals(events[0]['title'], doc[0]["subject"])
