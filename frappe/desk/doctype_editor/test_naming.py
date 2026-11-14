# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.desk.doctype_editor.naming import get_series_counters
from frappe.desk.doctype_editor.test_load import MANAGER, READER, a_user, developer_mode
from frappe.tests import IntegrationTestCase
from frappe.tests.classes.context_managers import set_user


class TestSeriesCounters(IntegrationTestCase):
	def tearDown(self):
		frappe.db.rollback()

	def counters(self, user: str, prefixes: list[str], mode: str = "Design", doctype: str = "ToDo") -> dict:
		with developer_mode(True), set_user(user):
			return get_series_counters(doctype, mode, frappe.as_json(prefixes))

	def test_reads_each_counter_without_moving_it(self):
		frappe.db.sql("delete from `tabSeries` where name in ('ED-47277-', 'ED-47277-NEW-')")
		frappe.db.sql("insert into `tabSeries` (name, current) values ('ED-47277-', 41)")
		manager = a_user(MANAGER, "System Manager")
		counters = self.counters(manager, ["ED-47277-", "ED-47277-NEW-"])
		self.assertEqual(counters, {"ED-47277-": 41, "ED-47277-NEW-": 0})
		self.assertEqual(self.counters(manager, ["ED-47277-"]), {"ED-47277-": 41})

	def test_needs_the_editor_mode(self):
		with self.assertRaises(frappe.PermissionError):
			self.counters(a_user(READER), ["ED-47277-"])

	def test_reads_the_counters_a_doctype_not_yet_created_will_use(self):
		frappe.db.sql("delete from `tabSeries` where name = 'ED-47280-'")
		frappe.db.sql("insert into `tabSeries` (name, current) values ('ED-47280-', 25)")
		manager = a_user(MANAGER, "System Manager")
		self.assertEqual(self.counters(manager, ["ED-47280-"], doctype="Ed 47280 New"), {"ED-47280-": 25})
		with self.assertRaises(frappe.PermissionError):
			self.counters(a_user(READER), ["ED-47280-"], doctype="Ed 47280 New")
		with self.assertRaises(frappe.ValidationError):
			self.counters(manager, ["ED-47280-"], mode="Customize", doctype="Ed 47280 New")

	def test_refuses_a_long_list(self):
		with self.assertRaises(frappe.ValidationError):
			self.counters(a_user(MANAGER, "System Manager"), [f"P{i}-" for i in range(51)])

	def test_refuses_prefixes_that_are_not_a_list_of_text(self):
		manager = a_user(MANAGER, "System Manager")
		for prefixes in ({"ED-47277-": 1}, "ED-47277-", [["ED-47277-"]], [7]):
			with self.subTest(prefixes=prefixes), self.assertRaises(frappe.ValidationError):
				self.counters(manager, prefixes)
