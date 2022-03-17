# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import unittest
import frappe
from frappe.utils import now_datetime

from frappe.model.naming import getseries
from frappe.model.naming import append_number_if_name_exists, revert_series_if_last
from frappe.model.naming import determine_consecutive_week_number, parse_naming_series

class TestNaming(unittest.TestCase):
	def setUp(self):
		frappe.db.delete('Note')

	def tearDown(self):
		frappe.db.rollback()

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

	def test_format_autoname_for_consecutive_week_number(self):
		'''
		Test if braced params are replaced for consecutive week number in format autoname
		'''
		doctype = 'ToDo'

		todo_doctype = frappe.get_doc('DocType', doctype)
		todo_doctype.autoname = 'format:TODO-{WW}-{##}'
		todo_doctype.save()

		description = 'Format'

		todo = frappe.new_doc(doctype)
		todo.description = description
		todo.insert()

		series = getseries('', 2)

		series = str(int(series)-1)

		if len(series) < 2:
			series = '0' + series

		week = determine_consecutive_week_number(now_datetime())

		self.assertEqual(todo.name, 'TODO-{week}-{series}'.format(
			week=week, series=series))

	def test_revert_series(self):
		from datetime import datetime
		year = datetime.now().year

		series = 'TEST-{}-'.format(year)
		key = 'TEST-.YYYY.-'
		name = 'TEST-{}-00001'.format(year)
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 1)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(current_index.get('current'), 0)
		frappe.db.delete("Series", {"name": series})

		series = 'TEST-{}-'.format(year)
		key = 'TEST-.YYYY.-.#####'
		name = 'TEST-{}-00002'.format(year)
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 2)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(current_index.get('current'), 1)
		frappe.db.delete("Series", {"name": series})

		series = 'TEST-'
		key = 'TEST-'
		name = 'TEST-00003'
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(current_index.get('current'), 2)
		frappe.db.delete("Series", {"name": series})

		series = 'TEST1-'
		key = 'TEST1-.#####.-2021-22'
		name = 'TEST1-00003-2021-22'
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(current_index.get('current'), 2)
		frappe.db.delete("Series", {"name": series})

		series = ''
		key = '.#####.-2021-22'
		name = '00003-2021-22'
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql("""SELECT current from `tabSeries` where name = %s""", series, as_dict=True)[0]

		self.assertEqual(current_index.get('current'), 2)

		frappe.db.delete("Series", {"name": series})

	def test_naming_for_cancelled_and_amended_doc(self):
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
		self.assertEqual(cancelled_name, original_name)

		amended_doc = frappe.copy_doc(doc)
		amended_doc.docstatus = 0
		amended_doc.amended_from = doc.name
		amended_doc.save()
		self.assertEqual(amended_doc.name, "{}-1".format(original_name))

		amended_doc.submit()
		amended_doc.cancel()
		self.assertEqual(amended_doc.name, "{}-1".format(original_name))

		submittable_doctype.delete()


	def test_determine_consecutive_week_number(self):
		from datetime import datetime

		dt = datetime.fromisoformat("2019-12-31")
		w = determine_consecutive_week_number(dt)
		self.assertEqual(w, "53")

		dt = datetime.fromisoformat("2020-01-01")
		w = determine_consecutive_week_number(dt)
		self.assertEqual(w, "01")

		dt = datetime.fromisoformat("2020-01-15")
		w = determine_consecutive_week_number(dt)
		self.assertEqual(w, "03")

		dt = datetime.fromisoformat("2021-01-01")
		w = determine_consecutive_week_number(dt)
		self.assertEqual(w, "00")

		dt = datetime.fromisoformat("2021-12-31")
		w = determine_consecutive_week_number(dt)
		self.assertEqual(w, "52")

	def test_naming_validations(self):
		# case 1: check same name as doctype
		# set name via prompt
		tag = frappe.get_doc({
			'doctype': 'Tag',
			'__newname': 'Tag'
		})
		self.assertRaises(frappe.NameError, tag.insert)

		# set by passing set_name as ToDo
		self.assertRaises(frappe.NameError, make_invalid_todo)

		# set new name - Note
		note = frappe.get_doc({
			'doctype': 'Note',
			'title': 'Note'
		})
		self.assertRaises(frappe.NameError, note.insert)

		# case 2: set name with "New ---"
		tag = frappe.get_doc({
			'doctype': 'Tag',
			'__newname': 'New Tag'
		})
		self.assertRaises(frappe.NameError, tag.insert)

		# case 3: set name with special characters
		tag = frappe.get_doc({
			'doctype': 'Tag',
			'__newname': 'Tag<>'
		})
		self.assertRaises(frappe.NameError, tag.insert)

		# case 4: no name specified
		tag = frappe.get_doc({
			'doctype': 'Tag',
			'__newname': ''
		})
		self.assertRaises(frappe.ValidationError, tag.insert)

	def test_autoincremented_naming(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		doctype = "autoinc_doctype" + frappe.generate_hash(length=5)
		dt = new_doctype(doctype, autoincremented=True).insert(ignore_permissions=True)

		for i in range(1, 20):
			self.assertEqual(frappe.new_doc(doctype).save(ignore_permissions=True).name, i)

		dt.delete(ignore_permissions=True)


def make_invalid_todo():
	frappe.get_doc({
		'doctype': 'ToDo',
		'description': 'Test'
	}).insert(set_name='ToDo')
