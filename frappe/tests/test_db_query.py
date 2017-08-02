# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt
from __future__ import unicode_literals

import frappe, unittest

from frappe.model.db_query import DatabaseQuery
from frappe.desk.reportview import get_filters_cond

class TestReportview(unittest.TestCase):
	def test_basic(self):
		self.assertTrue({"name":"DocType"} in DatabaseQuery("DocType").execute(limit_page_length=None))

	def test_fields(self):
		self.assertTrue({"name":"DocType", "issingle":0} \
			in DatabaseQuery("DocType").execute(fields=["name", "issingle"], limit_page_length=None))

	def test_filters_1(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[["DocType", "name", "like", "J%"]]))

	def test_filters_2(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters=[{"name": ["like", "J%"]}]))

	def test_filters_3(self):
		self.assertFalse({"name":"DocType"} \
			in DatabaseQuery("DocType").execute(filters={"name": ["like", "J%"]}))

	def test_filters_4(self):
		self.assertTrue({"name":"DocField"} \
			in DatabaseQuery("DocType").execute(filters={"name": "DocField"}))

	def test_in_not_in_filters(self):
		self.assertFalse(DatabaseQuery("DocType").execute(filters={"name": ["in", None]}))
		self.assertTrue({"name":"DocType"} \
				in DatabaseQuery("DocType").execute(filters={"name": ["not in", None]}))

		for result in [{"name":"DocType"}, {"name":"DocField"}]:
			self.assertTrue(result
				in DatabaseQuery("DocType").execute(filters={"name": ["in", 'DocType,DocField']}))

		for result in [{"name":"DocType"}, {"name":"DocField"}]:
			self.assertFalse(result
				in DatabaseQuery("DocType").execute(filters={"name": ["not in", 'DocType,DocField']}))

	def test_or_filters(self):
		data = DatabaseQuery("DocField").execute(
				filters={"parent": "DocType"}, fields=["fieldname", "fieldtype"],
				or_filters=[{"fieldtype":"Table"}, {"fieldtype":"Select"}])

		self.assertTrue({"fieldtype":"Table", "fieldname":"fields"} in data)
		self.assertTrue({"fieldtype":"Select", "fieldname":"document_type"} in data)
		self.assertFalse({"fieldtype":"Check", "fieldname":"issingle"} in data)

	def test_between_filters(self):
		""" test case to check between filter for date fields """
		frappe.db.sql("delete from tabEvent")

		# create events to test the between operator filter
		todays_event = create_event()
		event = create_event(starts_on="2016-07-06 12:00:00")

		# if the values are not passed in filters then todays event should be return
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", None]}, fields=["name"])

		self.assertTrue({ "name": todays_event.name } in data)
		self.assertTrue({ "name": event.name } not in data)

		# if both from and to_date values are passed
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-05 12:00:00", "2016-07-07 12:00:00"]]},
			fields=["name"])

		self.assertTrue({ "name": event.name } in data)
		self.assertTrue({ "name": todays_event.name } not in data)

		# if only one value is passed in the filter
		data = DatabaseQuery("Event").execute(
			filters={"starts_on": ["between", ["2016-07-05 12:00:00"]]},
			fields=["name"])

		self.assertTrue({ "name": todays_event.name } in data)
		self.assertTrue({ "name": event.name } in data)

	def test_ignore_permissions_for_get_filters_cond(self):
		frappe.set_user('test1@example.com')
		self.assertRaises(frappe.PermissionError, get_filters_cond, 'DocType', dict(istable=1), [])
		self.assertTrue(get_filters_cond('DocType', dict(istable=1), [], ignore_permissions=True))
		frappe.set_user('Administrator')

def create_event(subject="_Test Event", starts_on=None):
	""" create a test event """

	from frappe.utils import get_datetime

	event = frappe.get_doc({
		"doctype": "Event",
		"subject": subject,
		"event_type": "Public",
		"starts_on": get_datetime(starts_on),
	}).insert(ignore_permissions=True)

	return event