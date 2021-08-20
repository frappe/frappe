# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# MIT License. See license.txt

from __future__ import unicode_literals
import unittest
import frappe
from frappe.utils import now_datetime
from frappe.tests import update_system_settings

from frappe.model.naming import getseries
from frappe.model.naming import append_number_if_name_exists, revert_series_if_last

class TestNaming(unittest.TestCase):
	def tearDown(self):
		# Reset ToDo autoname to hash
		todo_doctype = frappe.get_doc('DocType', 'ToDo')
		todo_doctype.autoname = 'hash'
		todo_doctype.save()

	def test_append_number_if_name_exists(self):
		'''
		Append number to name based on existing values
		if Bottle exists
			Bottle -> Bottle-1
		if Bottle-1 exists
			Bottle -> Bottle-2
		'''

		note = frappe.new_doc('Note')
		note.title = 'Test'
		note.insert()

		title2 = append_number_if_name_exists('Note', 'Test')
		self.assertEqual(title2, 'Test-1')

		title2 = append_number_if_name_exists('Note', 'Test', 'title', '_')
		self.assertEqual(title2, 'Test_1')

	def test_format_autoname(self):
		'''
		Test if braced params are replaced in format autoname
		'''
		doctype = 'ToDo'

		todo_doctype = frappe.get_doc('DocType', doctype)
		todo_doctype.autoname = 'format:TODO-{MM}-{status}-{##}'
		todo_doctype.save()

		description = 'Format'

		todo = frappe.new_doc(doctype)
		todo.description = description
		todo.insert()

		series = getseries('', 2)

		series = str(int(series)-1)

		if len(series) < 2:
			series = '0' + series

		self.assertEqual(todo.name, 'TODO-{month}-{status}-{series}'.format(
			month=now_datetime().strftime('%m'), status=todo.status, series=series))

	def test_revert_series(self):
		from datetime import datetime
		year = datetime.now().year

		series = 'TEST-{}-'.format(year)
		key = 'TEST-.YYYY.-'
		name = 'TEST-{}-00001'.format(year)
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 1)""", (series,))
		revert_series_if_last(key, name)
		count = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(count.get('current'), 0)
		frappe.db.sql("""delete from `tabSeries` where name = %s""", series)

		series = 'TEST-{}-'.format(year)
		key = 'TEST-.YYYY.-.#####'
		name = 'TEST-{}-00002'.format(year)
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 2)""", (series,))
		revert_series_if_last(key, name)
		count = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(count.get('current'), 1)
		frappe.db.sql("""delete from `tabSeries` where name = %s""", series)

		series = 'TEST-'
		key = 'TEST-'
		name = 'TEST-00003'
		frappe.db.sql("DELETE FROM `tabSeries` WHERE `name`=%s", series)
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		count = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(count.get('current'), 2)
		frappe.db.sql("""delete from `tabSeries` where name = %s""", series)

	def test_naming_for_cancelled_and_amended_doc(self):
		update_system_settings({'use_original_name_for_amended_document': 1})

		submittable_doctype = frappe.get_doc({
			"doctype": "DocType",
			"module": "Core",
			"custom": 1,
			"is_submittable": 1,
			"permissions": [{
				"role": "System Manager",
				"read": 1
			}],
			"name": 'Submittable Doctype'
		}).insert(ignore_if_duplicate=True)

		doc = frappe.new_doc('Submittable Doctype')
		doc.save()
		original_name = doc.name

		doc.submit()
		doc.cancel()
		cancelled_name = doc.name
		self.assertEqual(cancelled_name, "{}-CANC-0".format(original_name))

		amended_doc = frappe.copy_doc(doc)
		amended_doc.docstatus = 0
		amended_doc.amended_from = doc.name
		amended_doc.save()
		self.assertEqual(amended_doc.name, original_name)

		amended_doc.submit()
		amended_doc.cancel()
		self.assertEqual(amended_doc.name, "{}-CANC-1".format(original_name))

		submittable_doctype.delete()
