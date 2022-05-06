# -*- coding: utf-8 -*-
# Copyright (c) 2018, Frappe Technologies and Contributors
# See license.txt
from __future__ import unicode_literals

import unittest

import frappe
from frappe.automation.doctype.auto_repeat.auto_repeat import (
	create_repeated_entries,
	get_auto_repeat_entries,
	week_map,
)
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.utils import add_days, add_months, getdate, today


def add_custom_fields():
	df = dict(
		fieldname="auto_repeat",
		label="Auto Repeat",
		fieldtype="Link",
		insert_after="sender",
		options="Auto Repeat",
		hidden=1,
		print_hide=1,
		read_only=1,
	)
	create_custom_field("ToDo", df)


class TestAutoRepeat(unittest.TestCase):
	def setUp(self):
		if not frappe.db.sql(
			"SELECT `fieldname` FROM `tabCustom Field` WHERE `fieldname`='auto_repeat' and `dt`=%s", "Todo"
		):
			add_custom_fields()

	def test_daily_auto_repeat(self):
		todo = frappe.get_doc(
			dict(doctype="ToDo", description="test recurring todo", assigned_by="Administrator")
		).insert()

		doc = make_auto_repeat(reference_document=todo.name)
		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value(
			"ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name"
		)

		new_todo = frappe.get_doc("ToDo", new_todo)

		self.assertEqual(todo.get("description"), new_todo.get("description"))

	def test_weekly_auto_repeat(self):
		todo = frappe.get_doc(
			dict(doctype="ToDo", description="test weekly todo", assigned_by="Administrator")
		).insert()

		doc = make_auto_repeat(
			reference_doctype="ToDo",
			frequency="Weekly",
			reference_document=todo.name,
			start_date=add_days(today(), -7),
		)

		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		new_todo = frappe.db.get_value(
			"ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name"
		)

		new_todo = frappe.get_doc("ToDo", new_todo)

		self.assertEqual(todo.get("description"), new_todo.get("description"))

	def test_weekly_auto_repeat_with_weekdays(self):
		todo = frappe.get_doc(
			dict(doctype="ToDo", description="test auto repeat with weekdays", assigned_by="Administrator")
		).insert()

		weekdays = list(week_map.keys())
		current_weekday = getdate().weekday()
		days = [{"day": weekdays[current_weekday]}, {"day": weekdays[(current_weekday + 2) % 7]}]
		doc = make_auto_repeat(
			reference_doctype="ToDo",
			frequency="Weekly",
			reference_document=todo.name,
			start_date=add_days(today(), -7),
			days=days,
		)

		self.assertEqual(doc.next_schedule_date, today())
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		todo = frappe.get_doc(doc.reference_doctype, doc.reference_document)
		self.assertEqual(todo.auto_repeat, doc.name)

		doc.reload()
		self.assertEqual(doc.next_schedule_date, add_days(getdate(), 2))

	def test_monthly_auto_repeat(self):
		start_date = today()
		end_date = add_months(start_date, 12)

		todo = frappe.get_doc(
			dict(doctype="ToDo", description="test recurring todo", assigned_by="Administrator")
		).insert()

		self.monthly_auto_repeat("ToDo", todo.name, start_date, end_date)
		# test without end_date
		todo = frappe.get_doc(
			dict(
				doctype="ToDo", description="test recurring todo without end_date", assigned_by="Administrator"
			)
		).insert()
		self.monthly_auto_repeat("ToDo", todo.name, start_date)

	def monthly_auto_repeat(self, doctype, docname, start_date, end_date=None):
		def get_months(start, end):
			diff = (12 * end.year + end.month) - (12 * start.year + start.month)
			return diff + 1

		doc = make_auto_repeat(
			reference_doctype=doctype,
			frequency="Monthly",
			reference_document=docname,
			start_date=start_date,
			end_date=end_date,
		)

		doc.disable_auto_repeat()

		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		docnames = frappe.get_all(doc.reference_doctype, {"auto_repeat": doc.name})
		self.assertEqual(len(docnames), 1)

		doc = frappe.get_doc("Auto Repeat", doc.name)
		doc.db_set("disabled", 0)

		months = get_months(getdate(start_date), getdate(today()))
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)

		docnames = frappe.get_all(doc.reference_doctype, {"auto_repeat": doc.name})
		self.assertEqual(len(docnames), months)

	def test_notification_is_attached(self):
		todo = frappe.get_doc(
			dict(
				doctype="ToDo",
				description="Test recurring notification attachment",
				assigned_by="Administrator",
			)
		).insert()

		doc = make_auto_repeat(
			reference_document=todo.name,
			notify=1,
			recipients="test@domain.com",
			subject="New ToDo",
			message="A new ToDo has just been created for you",
		)
		data = get_auto_repeat_entries(getdate(today()))
		create_repeated_entries(data)
		frappe.db.commit()

		new_todo = frappe.db.get_value(
			"ToDo", {"auto_repeat": doc.name, "name": ("!=", todo.name)}, "name"
		)

		linked_comm = frappe.db.exists(
			"Communication", dict(reference_doctype="ToDo", reference_name=new_todo)
		)
		self.assertTrue(linked_comm)

	def test_next_schedule_date(self):
		current_date = getdate(today())
		todo = frappe.get_doc(
			dict(
				doctype="ToDo", description="test next schedule date for monthly", assigned_by="Administrator"
			)
		).insert()
		doc = make_auto_repeat(
			frequency="Monthly", reference_document=todo.name, start_date=add_months(today(), -2)
		)

		# next_schedule_date is set as on or after current date
		# it should not be a previous month's date
		self.assertTrue((doc.next_schedule_date >= current_date))

		todo = frappe.get_doc(
			dict(
				doctype="ToDo", description="test next schedule date for daily", assigned_by="Administrator"
			)
		).insert()
		doc = make_auto_repeat(
			frequency="Daily", reference_document=todo.name, start_date=add_days(today(), -2)
		)
		self.assertEqual(getdate(doc.next_schedule_date), current_date)

	def test_submit_on_creation(self):
		doctype = "Test Submittable DocType"
		create_submittable_doctype(doctype)

		current_date = getdate()
		submittable_doc = frappe.get_doc(dict(doctype=doctype, test="test submit on creation")).insert()
		submittable_doc.submit()
		doc = make_auto_repeat(
			frequency="Daily",
			reference_doctype=doctype,
			reference_document=submittable_doc.name,
			start_date=add_days(current_date, -1),
			submit_on_creation=1,
		)

		data = get_auto_repeat_entries(current_date)
		create_repeated_entries(data)
		docnames = frappe.db.get_all(
			doc.reference_doctype, filters={"auto_repeat": doc.name}, fields=["docstatus"], limit=1
		)
		self.assertEquals(docnames[0].docstatus, 1)


def make_auto_repeat(**args):
	args = frappe._dict(args)
	doc = frappe.get_doc(
		{
			"doctype": "Auto Repeat",
			"reference_doctype": args.reference_doctype or "ToDo",
			"reference_document": args.reference_document or frappe.db.get_value("ToDo", "name"),
			"submit_on_creation": args.submit_on_creation or 0,
			"frequency": args.frequency or "Daily",
			"start_date": args.start_date or add_days(today(), -1),
			"end_date": args.end_date or "",
			"notify_by_email": args.notify or 0,
			"recipients": args.recipients or "",
			"subject": args.subject or "",
			"message": args.message or "",
			"repeat_on_days": args.days or [],
		}
	).insert(ignore_permissions=True)

	return doc


def create_submittable_doctype(doctype, submit_perms=1):
	if frappe.db.exists("DocType", doctype):
		return
	else:
		doc = frappe.get_doc(
			{
				"doctype": "DocType",
				"__newname": doctype,
				"module": "Custom",
				"custom": 1,
				"is_submittable": 1,
				"fields": [{"fieldname": "test", "label": "Test", "fieldtype": "Data"}],
				"permissions": [
					{
						"role": "System Manager",
						"read": 1,
						"write": 1,
						"create": 1,
						"delete": 1,
						"submit": submit_perms,
						"cancel": submit_perms,
						"amend": submit_perms,
					}
				],
			}
		).insert()

		doc.allow_auto_repeat = 1
		doc.save()
