# Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.model.naming import (
	InvalidNamingSeriesError,
	NamingSeries,
	append_number_if_name_exists,
	determine_consecutive_week_number,
	getseries,
	parse_naming_series,
	revert_series_if_last,
)
from frappe.tests.utils import FrappeTestCase
from frappe.utils import now_datetime, nowdate, nowtime


class TestNaming(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("Note")

	def tearDown(self):
		frappe.db.rollback()

	def test_append_number_if_name_exists(self):
		"""
		Append number to name based on existing values
		if Bottle exists
		        Bottle -> Bottle-1
		if Bottle-1 exists
		        Bottle -> Bottle-2
		"""

		note = frappe.new_doc("Note")
		note.title = "Test"
		note.insert()

		title2 = append_number_if_name_exists("Note", "Test")
		self.assertEqual(title2, "Test-1")

		title2 = append_number_if_name_exists("Note", "Test", "title", "_")
		self.assertEqual(title2, "Test_1")

	def test_field_autoname_name_sync(self):

		country = frappe.get_last_doc("Country")
		original_name = country.name
		country.country_name = "Not a country"
		country.save()
		country.reload()

		self.assertEqual(country.name, original_name)
		self.assertEqual(country.name, country.country_name)

	def test_child_table_naming(self):
		child_dt_with_naming = new_doctype(istable=1, autoname="field:some_fieldname").insert()
		dt_with_child_autoname = new_doctype(
			fields=[
				{
					"label": "table with naming",
					"fieldname": "table_with_naming",
					"options": child_dt_with_naming.name,
					"fieldtype": "Table",
				}
			],
		).insert()

		name = frappe.generate_hash(length=10)

		doc = frappe.new_doc(dt_with_child_autoname.name)
		doc.append("table_with_naming", {"some_fieldname": name})
		doc.save()
		self.assertEqual(doc.table_with_naming[0].name, name)

		# change autoname field
		doc.table_with_naming[0].some_fieldname = "Something else"
		doc.save()

		self.assertEqual(doc.table_with_naming[0].name, name)
		self.assertEqual(doc.table_with_naming[0].some_fieldname, name)

		doc.delete()
		dt_with_child_autoname.delete()
		child_dt_with_naming.delete()

	def test_format_autoname(self):
		"""
		Test if braced params are replaced in format autoname
		"""
		doctype = new_doctype(autoname="format:TODO-{MM}-{some_fieldname}-{##}").insert()

		description = "Format"

		doc = frappe.new_doc(doctype.name)
		doc.some_fieldname = description
		doc.insert()

		series = getseries("", 2)
		series = int(series) - 1

		self.assertEqual(doc.name, f"TODO-{now_datetime().strftime('%m')}-{description}-{series:02}")

	def test_format_autoname_for_datetime_field(self):
		"""Test if datetime, date and time objects get converted to strings for naming."""
		doctype = new_doctype(autoname="format:TODO-{field}-{##}").insert()

		for field in [now_datetime(), nowdate(), nowtime()]:
			doc = frappe.new_doc(doctype.name)
			doc.field = field
			doc.insert()

			series = getseries("", 2)
			series = int(series) - 1

			self.assertEqual(doc.name, f"TODO-{field}-{series:02}")

	def test_format_autoname_for_consecutive_week_number(self):
		"""
		Test if braced params are replaced for consecutive week number in format autoname
		"""
		doctype = "ToDo"

		todo_doctype = frappe.get_doc("DocType", doctype)
		todo_doctype.autoname = "format:TODO-{WW}-{##}"
		todo_doctype.save()

		description = "Format"

		todo = frappe.new_doc(doctype)
		todo.description = description
		todo.insert()

		series = getseries("", 2)

		series = str(int(series) - 1)

		if len(series) < 2:
			series = "0" + series

		week = determine_consecutive_week_number(now_datetime())

		self.assertEqual(todo.name, f"TODO-{week}-{series}")

	def test_revert_series(self):
		from datetime import datetime

		year = datetime.now().year

		series = f"TEST-{year}-"
		key = "TEST-.YYYY.-"
		name = f"TEST-{year}-00001"
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 1)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql(
			"""SELECT current from `tabSeries` where name = %s""", series, as_dict=True
		)[0]

		self.assertEqual(current_index.get("current"), 0)
		frappe.db.delete("Series", {"name": series})

		series = f"TEST-{year}-"
		key = "TEST-.YYYY.-.#####"
		name = f"TEST-{year}-00002"
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 2)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql(
			"""SELECT current from `tabSeries` where name = %s""", series, as_dict=True
		)[0]

		self.assertEqual(current_index.get("current"), 1)
		frappe.db.delete("Series", {"name": series})

		series = "TEST-"
		key = "TEST-"
		name = "TEST-00003"
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql(
			"""SELECT current from `tabSeries` where name = %s""", series, as_dict=True
		)[0]

		self.assertEqual(current_index.get("current"), 2)
		frappe.db.delete("Series", {"name": series})

		series = "TEST1-"
		key = "TEST1-.#####.-2021-22"
		name = "TEST1-00003-2021-22"
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql(
			"""SELECT current from `tabSeries` where name = %s""", series, as_dict=True
		)[0]

		self.assertEqual(current_index.get("current"), 2)
		frappe.db.delete("Series", {"name": series})

		series = ""
		key = ".#####.-2021-22"
		name = "00003-2021-22"
		frappe.db.delete("Series", {"name": series})
		frappe.db.sql("""INSERT INTO `tabSeries` (name, current) values (%s, 3)""", (series,))
		revert_series_if_last(key, name)
		current_index = frappe.db.sql(
			"""SELECT current from `tabSeries` where name = %s""", series, as_dict=True
		)[0]

		self.assertEqual(current_index.get("current"), 2)

		frappe.db.delete("Series", {"name": series})

	def test_naming_for_cancelled_and_amended_doc(self):
		submittable_doctype = frappe.get_doc(
			{
				"doctype": "DocType",
				"module": "Core",
				"custom": 1,
				"is_submittable": 1,
				"permissions": [{"role": "System Manager", "read": 1}],
				"name": "Submittable Doctype",
			}
		).insert(ignore_if_duplicate=True)

		doc = frappe.new_doc("Submittable Doctype")
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
		self.assertEqual(amended_doc.name, f"{original_name}-1")

		amended_doc.submit()
		amended_doc.cancel()
		self.assertEqual(amended_doc.name, f"{original_name}-1")

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
		tag = frappe.get_doc({"doctype": "Tag", "__newname": "Tag"})
		self.assertRaises(frappe.NameError, tag.insert)

		# set by passing set_name as ToDo
		self.assertRaises(frappe.NameError, make_invalid_todo)

		# set new name - Note
		note = frappe.get_doc({"doctype": "Note", "title": "Note"})
		self.assertRaises(frappe.NameError, note.insert)

		# case 2: set name with "New ---"
		tag = frappe.get_doc({"doctype": "Tag", "__newname": "New Tag"})
		self.assertRaises(frappe.NameError, tag.insert)

		# case 3: set name with special characters
		tag = frappe.get_doc({"doctype": "Tag", "__newname": "Tag<>"})
		self.assertRaises(frappe.NameError, tag.insert)

		# case 4: no name specified
		tag = frappe.get_doc({"doctype": "Tag", "__newname": ""})
		self.assertRaises(frappe.ValidationError, tag.insert)

	def test_autoincremented_naming(self):
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		doctype = "autoinc_doctype" + frappe.generate_hash(length=5)
		dt = new_doctype(doctype, autoname="autoincrement").insert(ignore_permissions=True)

		for i in range(1, 20):
			self.assertEqual(frappe.new_doc(doctype).save(ignore_permissions=True).name, i)

		dt.delete(ignore_permissions=True)

	def test_naming_series_prefix(self):
		today = now_datetime()
		year = today.strftime("%y")
		month = today.strftime("%m")

		prefix_test_cases = {
			"SINV-.YY.-.####": f"SINV-{year}-",
			"SINV-.YY.-.MM.-.####": f"SINV-{year}-{month}-",
			"SINV": "SINV",
			"SINV-.": "SINV-",
		}

		for series, prefix in prefix_test_cases.items():
			self.assertEqual(prefix, NamingSeries(series).get_prefix())

	def test_naming_series_validation(self):
		dns = frappe.get_doc("Document Naming Settings")
		exisiting_series = dns.get_transactions_and_prefixes()["prefixes"]
		valid = ["SINV-", "SI-.{field}.", "SI-#.###", ""] + exisiting_series
		invalid = ["$INV-", r"WINDOWS\NAMING"]

		for series in valid:
			if series.strip():
				try:
					NamingSeries(series).validate()
				except Exception as e:
					self.fail(f"{series} should be valid\n{e}")

		for series in invalid:
			self.assertRaises(InvalidNamingSeriesError, NamingSeries(series).validate)

	def test_naming_using_fields(self):

		webhook = frappe.new_doc("Webhook")
		webhook.webhook_docevent = "on_update"
		name = NamingSeries("KOOH-.{webhook_docevent}.").generate_next_name(webhook)
		self.assertTrue(
			name.startswith("KOOH-on_update"), f"incorrect name generated {name}, missing field value"
		)

	def test_naming_with_empty_part(self):
		# check naming with empty part (duplicate dots)

		webhook = frappe.new_doc("Webhook")
		webhook.webhook_docevent = "on_update"

		series = "KOOH-..{webhook_docevent}.-.####"

		name = parse_naming_series(series, doc=webhook)
		self.assertTrue(
			name.startswith("KOOH-on_update"), f"incorrect name generated {name}, missing field value"
		)

	def test_naming_with_unsupported_part(self):
		# check naming with empty part (duplicate dots)

		webhook = frappe.new_doc("Webhook")
		webhook.webhook_docevent = {"dict": "not supported"}

		series = "KOOH-..{webhook_docevent}.-.####"

		name = parse_naming_series(series, doc=webhook)
		self.assertTrue(
			name.startswith("KOOH-"), f"incorrect name generated {name}, missing field value"
		)

	def test_naming_with_empty_field(self):
		# check naming with empty field value

		webhook = frappe.new_doc("Webhook")
		series = "KOOH-.{request_structure}.-.request_structure.-.####"

		name = parse_naming_series(series, doc=webhook)
		self.assertTrue(name.startswith("KOOH---"), f"incorrect name generated {name}")


def make_invalid_todo():
	frappe.get_doc({"doctype": "ToDo", "description": "Test"}).insert(set_name="ToDo")
