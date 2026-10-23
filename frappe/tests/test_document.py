# Copyright (c) 2022, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import inspect
import pickle
from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
from unittest.mock import Mock, patch

import frappe
from frappe.app import make_form_dict
from frappe.core.doctype.doctype.test_doctype import new_doctype
from frappe.core.doctype.rq_job.test_rq_job import wait_for_completion
from frappe.core.doctype.user.user import User
from frappe.core.doctype.user_permission.test_user_permission import create_user
from frappe.deprecation_dumpster import FrappeDeprecationWarning
from frappe.desk.doctype.note.note import Note
from frappe.desk.doctype.todo.todo import ToDo
from frappe.model.base_document import BaseDocument
from frappe.model.document import Document, LazyChildTable, LazyDocument, _get_extended_class
from frappe.model.naming import make_autoname, parse_naming_series, revert_series_if_last
from frappe.tests import IntegrationTestCase
from frappe.utils import cint, get_datetime, now_datetime, set_request
from frappe.website.serve import get_response


class CustomTestNote(Note):
	@property
	def age(self):
		return now_datetime() - self.creation


class CustomNoteWithoutProperty(Note):
	def age(self):
		return now_datetime() - self.creation


class TestExtensionA(Document):
	def extension_method_a(self):
		return "method_a"


class TestExtensionB(Document):
	def extension_method_b(self):
		return "method_b"


class TestToDoExtension(Document):
	"""Extension class that overrides ToDo's validate method"""

	def validate(self):
		# Add our custom logic
		self.custom_validation_called = True

	def extension_method(self):
		return "extension_method_called"


class TestDocument(IntegrationTestCase):
	def test_get_return_empty_list_for_table_field_if_none(self):
		d = frappe.get_doc({"doctype": "User"})
		self.assertEqual(d.get("roles"), [])

	def test_load(self):
		d = frappe.get_doc("DocType", "User")
		self.assertEqual(d.doctype, "DocType")
		self.assertEqual(d.name, "User")
		self.assertEqual(d.allow_rename, 1)
		self.assertTrue(isinstance(d.fields, list))
		self.assertTrue(isinstance(d.permissions, list))
		self.assertTrue(filter(lambda d: d.fieldname == "email", d.fields))

	def test_load_single(self):
		d = frappe.get_doc("Website Settings", "Website Settings")
		self.assertEqual(d.name, "Website Settings")
		self.assertEqual(d.doctype, "Website Settings")
		self.assertTrue(d.disable_signup in (0, 1))

		with patch.object(frappe.db, "get_singles_dict", return_value=frappe._dict({"disable_signup": 0})):
			d = frappe.get_doc("Website Settings")
			self.assertEqual(d.name, "Website Settings")

	def test_insert(self):
		d = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test-doc-test-event 1",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		)
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEqual(frappe.db.get_value("Event", d.name, "subject"), "test-doc-test-event 1")

		# test if default values are added
		self.assertEqual(d.send_reminder, 1)
		return d

	def test_submittable_insert(self):
		doctype_name = "Test Document Submittable"
		if frappe.db.exists("DocType", doctype_name):
			dt = frappe.get_doc("DocType", doctype_name)
		else:
			dt = frappe.get_doc(
				{
					"doctype": "DocType",
					"module": "Core",
					"name": doctype_name,
					"custom": 1,
					"is_submittable": 1,
					"fields": [{"label": "Field", "fieldname": "test_field", "fieldtype": "Data"}],
					"permissions": [
						{"role": "System Manager", "read": 1, "write": 1, "submit": 1, "cancel": 1}
					],
				}
			).insert()

		d = frappe.get_doc({"doctype": dt.name, "test_field": "test"}).insert()
		return d

	def test_website_route_default(self):
		default = frappe.generate_hash()
		child_table = new_doctype(default=default, istable=1).insert().name
		parent = (
			new_doctype(fields=[{"fieldtype": "Table", "options": child_table, "fieldname": "child_table"}])
			.insert()
			.name
		)

		doc = frappe.get_doc({"doctype": parent, "child_table": [{"some_fieldname": "xasd"}]}).insert()
		doc.append("child_table", {})
		doc.save()
		self.assertEqual(doc.child_table[-1].some_fieldname, default)

	def test_insert_with_child(self):
		d = frappe.get_doc(
			{
				"doctype": "Event",
				"subject": "test-doc-test-event 2",
				"starts_on": "2014-01-01",
				"event_type": "Public",
			}
		)
		d.insert()
		self.assertTrue(d.name.startswith("EV"))
		self.assertEqual(frappe.db.get_value("Event", d.name, "subject"), "test-doc-test-event 2")

	def test_update(self):
		d = self.test_insert()
		d.subject = "subject changed"
		d.save()

		self.assertEqual(frappe.db.get_value(d.doctype, d.name, "subject"), "subject changed")

	def test_discard_transitions(self):
		d = self.test_submittable_insert()
		self.assertEqual(d.docstatus, 0)

		# invalid: Submit > Discard, Cancel > Discard
		d.submit()
		self.assertRaises(frappe.ValidationError, d.discard)
		d.reload()

		d.cancel()
		self.assertRaises(frappe.ValidationError, d.discard)

		# valid: Draft > Discard
		d2 = self.test_submittable_insert()
		d2.discard()
		self.assertEqual(d2.docstatus, 2)

	def test_save_on_discard_throws(self):
		from frappe.desk.doctype.event.event import Event

		d3 = self.test_insert()

		def test_on_discard(d3):
			d3.subject = d3.subject + "update"
			d3.save()

		d3.on_discard = (test_on_discard)(d3)
		d3.on_discard = test_on_discard.__get__(d3, Event)

		self.assertRaises(frappe.ValidationError, d3.discard)

	def test_value_changed(self):
		d = self.test_insert()
		d.subject = "subject changed again"
		d.load_doc_before_save()
		d.update_modified()

		self.assertTrue(d.has_value_changed("subject"))
		self.assertTrue(d.has_value_changed("modified"))

		self.assertFalse(d.has_value_changed("creation"))
		self.assertFalse(d.has_value_changed("event_type"))

		user = frappe.get_doc("User", "Administrator")
		user.load_doc_before_save()
		role1 = user.roles[0]
		role2 = user.roles[1]

		role1.role = "New Role"

		self.assertTrue(role1.has_value_changed("role"))
		self.assertFalse(role2.has_value_changed("role"))

	def test_mandatory(self):
		# TODO: recheck if it is OK to force delete
		frappe.delete_doc_if_exists("User", "test_mandatory@example.com", 1)

		d = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_mandatory@example.com",
			}
		)
		self.assertRaises(frappe.MandatoryError, d.insert)

		d.set("first_name", "Test Mandatory")
		d.insert()
		self.assertEqual(frappe.db.get_value("User", d.name), d.name)

	def test_text_editor_field(self):
		try:
			frappe.get_doc(doctype="Activity Log", subject="test", message='<img src="test.png" />').insert()
		except frappe.MandatoryError:
			self.fail("Text Editor false positive mandatory error")

	def test_conflict_validation(self):
		d1 = self.test_insert()
		d2 = frappe.get_doc(d1.doctype, d1.name)
		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_save_after_insert_on_a_whole_second(self):
		with self.freeze_time("2026-10-15 10:33:29"):
			event = self.test_insert()

		event.subject = "saved after a whole-second insert"
		event.save()

		saved = frappe.db.get_value("Event", event.name, ["subject", "creation"], as_dict=True)
		self.assertEqual(saved.subject, "saved after a whole-second insert")
		self.assertEqual(saved.creation, get_datetime("2026-10-15 10:33:29"))

	def test_first_save_of_a_single(self):
		doctype = new_doctype(
			issingle=1, fields=[{"fieldname": "note", "fieldtype": "Data", "label": "Note"}]
		).insert()

		single = frappe.get_doc(doctype.name)
		single.note = "first save"
		single.save()

		self.assertEqual(frappe.db.get_single_value(doctype.name, "note"), "first save")

	def test_conflict_validation_single(self):
		d1 = frappe.get_doc("Website Settings", "Website Settings")
		d1.home_page = "test-web-page-1"

		d2 = frappe.get_doc("Website Settings", "Website Settings")
		d2.home_page = "test-web-page-1"

		d1.save()
		self.assertRaises(frappe.TimestampMismatchError, d2.save)

	def test_permission(self):
		frappe.set_user("Guest")
		self.assertRaises(frappe.PermissionError, self.test_insert)
		frappe.set_user("Administrator")

	def test_permission_single(self):
		frappe.set_user("Guest")
		d = frappe.get_doc("Website Settings", "Website Settings")
		self.assertRaises(frappe.PermissionError, d.save)
		frappe.set_user("Administrator")

	def test_link_validation(self):
		frappe.delete_doc_if_exists("User", "test_link_validation@example.com", 1)

		d = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_link_validation@example.com",
				"first_name": "Link Validation",
				"roles": [{"role": "ABC"}],
			}
		)
		self.assertRaises(frappe.LinkValidationError, d.insert)

		d.roles = []
		d.append("roles", {"role": "System Manager"})
		d.insert()

		self.assertEqual(frappe.db.get_value("User", d.name), d.name)

		d.append("roles", {"role": ("Guest", "Administrator")})
		self.assertRaises(AssertionError, d._validate_links)

	def test_validate(self):
		d = self.test_insert()
		d.starts_on = "2014-01-01"
		d.ends_on = "2013-01-01"
		self.assertRaises(frappe.ValidationError, d.validate)
		self.assertRaises(frappe.ValidationError, d.run_method, "validate")
		self.assertRaises(frappe.ValidationError, d.save)

	def test_db_set_no_query_on_new_docs(self):
		user = frappe.new_doc("User")
		user.db_set("user_type", "Magical Wizard")
		with self.assertQueryCount(0):
			user.db_set("user_type", "Magical Wizard")

	def test_new_doc_with_fields(self):
		user = frappe.new_doc("User", first_name="wizard")
		self.assertEqual(user.first_name, "wizard")

	def test_update_after_submit(self):
		d = self.test_insert()
		d.starts_on = "2014-09-09"
		self.assertRaises(frappe.UpdateAfterSubmitError, d.validate_update_after_submit)
		d.meta.get_field("starts_on").allow_on_submit = 1
		d.validate_update_after_submit()
		d.meta.get_field("starts_on").allow_on_submit = 0

		# when comparing date(2014, 1, 1) and "2014-01-01"
		d.reload()
		d.starts_on = "2014-01-01"
		d.validate_update_after_submit()

	def test_varchar_length(self):
		d = self.test_insert()
		d.sender = "abcde" * 100 + "@user.com"
		self.assertRaises(frappe.CharacterLengthExceededError, d.save)

	def test_varchar_length_after_sanitization(self):
		unclosed_tag = "<strong>"
		value = "X" * (140 - len(unclosed_tag)) + unclosed_tag

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Note")
			doc.title = value

			with self.assertRaises(frappe.CharacterLengthExceededError):
				doc._validate()

		self.assertGreater(len(doc.title), 140)

	def test_oversized_varchar_sanitized_within_limit(self):
		value = "X" * 130 + "<script>1</script>"
		self.assertGreater(len(value), 140)

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Note")
			doc.title = value
			doc._validate()

		self.assertEqual(doc.title, "X" * 130)

	def test_child_varchar_length_after_sanitization(self):
		unclosed_tag = "<strong>"
		value = "X" * (140 - len(unclosed_tag)) + unclosed_tag

		with self.set_user("test@example.com"):
			doc = frappe.new_doc("Workspace")
			doc.update(
				{"label": "Test Workspace", "module": "Core", "title": "Test Workspace", "type": "Workspace"}
			)
			doc.name = "Test Workspace"
			doc.append("shortcuts", {"type": "URL", "label": value})

			with self.assertRaises(frappe.CharacterLengthExceededError):
				doc._validate()

		self.assertGreater(len(doc.shortcuts[0].label), 140)

	def test_xss_filter(self):
		d = self.test_insert()
		subject = d.subject

		# script
		xss = '<script>alert("XSS")</script>'
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertEqual(subject, d.subject)

		# onload
		xss = '<div onload="alert("XSS")">Test</div>'
		escaped_xss = "<div>Test</div>"
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

		# css attributes
		xss = '<div style="something: doesn\'t work; color: red;">Test</div>'
		escaped_xss = '<div style="">Test</div>'
		d.subject += xss
		d.save()
		d.reload()

		self.assertTrue(xss not in d.subject)
		self.assertTrue(escaped_xss in d.subject)

	def test_naming_series(self):
		data = ["TEST-", "TEST/17-18/.test_data./.####", "TEST.YYYY.MM.####"]

		for series in data:
			name = make_autoname(series)
			prefix = series

			if ".#" in series:
				prefix = series.rsplit(".", 1)[0]

			prefix = parse_naming_series(prefix)
			old_current = frappe.db.get_value("Series", prefix, "current", order_by="name")

			revert_series_if_last(series, name)
			new_current = cint(frappe.db.get_value("Series", prefix, "current", order_by="name"))

			self.assertEqual(cint(old_current) - 1, new_current)

	def test_non_negative_check(self):
		frappe.delete_doc_if_exists("Currency", "Frappe Coin", 1)

		d = frappe.get_doc(
			{"doctype": "Currency", "currency_name": "Frappe Coin", "smallest_currency_fraction_value": -1}
		)

		self.assertRaises(frappe.NonNegativeError, d.insert)

		d.set("smallest_currency_fraction_value", 1)
		d.insert()
		self.assertEqual(frappe.db.get_value("Currency", d.name), d.name)

		frappe.delete_doc_if_exists("Currency", "Frappe Coin", 1)

	def test_min_max_value_check(self):
		doctype = new_doctype(
			fields=[
				{
					"fieldname": "qty",
					"fieldtype": "Int",
					"label": "Qty",
					"min_value": 5,
					"max_value": 10,
				}
			]
		).insert()

		try:
			self.assertRaises(frappe.ValidationError, frappe.get_doc(doctype=doctype.name, qty=3).insert)
			self.assertRaises(frappe.ValidationError, frappe.get_doc(doctype=doctype.name, qty=12).insert)
			frappe.get_doc(doctype=doctype.name, qty=7).insert()
			frappe.get_doc(doctype=doctype.name).insert()
		finally:
			doctype.delete(force=True)

	def test_get_formatted(self):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "Test Formatted",
				"module": "Custom",
				"custom": 1,
				"fields": [
					{"label": "Currency", "fieldname": "currency", "reqd": 1, "fieldtype": "Currency"},
				],
			}
		).insert(ignore_if_duplicate=True)

		frappe.delete_doc_if_exists("Currency", "INR", 1)

		d = frappe.get_doc(
			{
				"doctype": "Currency",
				"currency_name": "INR",
				"symbol": "₹",
			}
		).insert()

		d = frappe.get_doc({"doctype": "Test Formatted", "currency": 100000})
		self.assertEqual(d.get_formatted("currency", currency="INR", format="#,###.##"), "₹ 100,000.00")

		# should work even if options aren't set in df
		# and currency param is not passed
		self.assertIn("0", d.get_formatted("currency"))

	def test_limit_for_get(self):
		doc = frappe.get_doc("DocType", "DocType")
		# assuming DocType has more than 3 Data fields
		self.assertEqual(len(doc.get("fields", limit=3)), 3)

		# limit with filters
		self.assertEqual(len(doc.get("fields", filters={"fieldtype": "Data"}, limit=3)), 3)

	def test_virtual_fields(self):
		"""Virtual fields are accessible via API and Form views, whenever .as_dict is invoked"""
		frappe.db.delete("Custom Field", {"dt": "Note", "fieldname": "age"})
		note = frappe.new_doc("Note")
		note.content = "some content"
		note.title = frappe.generate_hash(length=20)
		note.insert()

		def patch_note(class_=None):
			return patch("frappe.controllers", new={frappe.local.site: {"Note": class_ or CustomTestNote}})

		@contextmanager
		def customize_note(with_options=False):
			options = (
				"frappe.utils.now_datetime() - frappe.utils.get_datetime(doc.creation)"
				if with_options
				else ""
			)
			custom_field = frappe.get_doc(
				{
					"doctype": "Custom Field",
					"dt": "Note",
					"fieldname": "age",
					"fieldtype": "Data",
					"read_only": True,
					"is_virtual": True,
					"options": options,
				}
			)

			try:
				yield custom_field.insert(ignore_if_duplicate=True)
			finally:
				custom_field.delete()
				# to truly delete the field
				# creation is commited due to DDL
				frappe.db.commit()

		with patch_note():
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomTestNote)
			self.assertIsInstance(doc.age, timedelta)
			self.assertIsNone(doc.as_dict().get("age"))
			self.assertIsNone(doc.get_valid_dict().get("age"))

		with customize_note(), patch_note():
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomTestNote)
			self.assertIsInstance(doc.age, timedelta)
			self.assertIsInstance(doc.as_dict().get("age"), timedelta)
			self.assertIsInstance(doc.get_valid_dict().get("age"), timedelta)

		# has virtual field, but age method is not a property
		with customize_note(), patch_note(class_=CustomNoteWithoutProperty):
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, CustomNoteWithoutProperty)
			self.assertNotIsInstance(type(doc).age, property)
			self.assertIsNone(doc.as_dict().get("age"))
			self.assertIsNone(doc.get_valid_dict().get("age"))

		with customize_note(with_options=True):
			doc = frappe.get_last_doc("Note")
			self.assertIsInstance(doc, Note)
			self.assertIsInstance(doc.as_dict().get("age"), timedelta)
			self.assertIsInstance(doc.get_valid_dict().get("age"), timedelta)

	def test_virtual_fields_of_single_are_not_stored(self):
		doctype = new_doctype(
			issingle=1,
			fields=[
				{"fieldname": "title", "fieldtype": "Data", "label": "Title"},
				{
					"fieldname": "loud_title",
					"fieldtype": "Data",
					"label": "Loud Title",
					"is_virtual": 1,
					"options": "(doc.title or '').upper()",
				},
			],
			permissions=[{"role": "_Test Role", "read": 1, "write": 1, "create": 1}],
		).insert()
		self.addCleanup(doctype.delete, force=True)
		user = create_user("test_single_virtual_fields@example.com", "_Test Role")

		def assert_virtual_field_not_stored(expected_value):
			self.assertEqual(frappe.db.count("Singles", {"doctype": doctype.name, "field": "loud_title"}), 0)
			self.assertEqual(frappe.get_doc(doctype.name).as_dict().loud_title, expected_value)

		with self.set_user(user.name):
			single = frappe.get_doc({"doctype": doctype.name, "title": "hello"}).insert()
			assert_virtual_field_not_stored("HELLO")

			single.title = "bye"
			single.save()
			assert_virtual_field_not_stored("BYE")

	def test_run_method(self):
		doc = frappe.get_last_doc("User")

		# Case 1: Override with a string
		doc.as_dict = ""

		# run_method should throw TypeError
		self.assertRaisesRegex(TypeError, "not callable", doc.run_method, "as_dict")

		# Case 2: Override with a function
		def my_as_dict(*args, **kwargs):
			return "success"

		doc.as_dict = my_as_dict

		# run_method should get overridden
		self.assertEqual(doc.run_method("as_dict"), "success")

	def test_extend(self):
		doc = frappe.get_last_doc("User")
		self.assertRaises(ValueError, doc.extend, "user_emails", None)

		# allow calling doc.extend with iterable objects
		doc.extend("user_emails", ())
		doc.extend("user_emails", [])
		doc.extend("user_emails", (x for x in ()))

	def test_set(self):
		doc = frappe.get_last_doc("User")

		# setting None should init a table field to empty list
		doc.set("user_emails", None)
		self.assertEqual(doc.user_emails, [])

		# setting a string value should fail
		self.assertRaises(TypeError, doc.set, "user_emails", "fail")
		# but not when loading from db
		doc.flags.ignore_children = True
		doc.update({"user_emails": "ok"})

	def test_doc_events(self):
		"""validate that all present doc events are correct methods"""

		for doctype, doc_hooks in frappe.get_doc_hooks().items():
			for _, hooks in doc_hooks.items():
				for hook in hooks:
					try:
						frappe.get_attr(hook)
					except Exception as e:
						self.fail(f"Invalid doc hook: {doctype}:{hook}\n{e}")

	def test_realtime_notify(self):
		todo = frappe.new_doc("ToDo")
		todo.description = "this will trigger realtime update"
		todo.notify_update = Mock()
		todo.insert()
		self.assertEqual(todo.notify_update.call_count, 1)

		todo.reload()
		todo.flags.notify_update = False
		todo.description = "this won't trigger realtime update"
		todo.save()
		self.assertEqual(todo.notify_update.call_count, 1)

	def test_error_on_saving_new_doc_with_name(self):
		"""Trying to save a new doc with name should raise DoesNotExistError"""

		doc = frappe.get_doc(
			{
				"doctype": "ToDo",
				"description": "this should raise frappe.DoesNotExistError",
				"name": "lets-trick-doc-save",
			}
		)

		self.assertRaises(frappe.DoesNotExistError, doc.save)

	def test_validate_from_to_dates(self):
		doc = frappe.new_doc("Web Page")
		doc.start_date = None
		doc.end_date = None
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = "2020-01-01"
		doc.end_date = None
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = None
		doc.end_date = "2020-12-31"
		doc.validate_from_to_dates("start_date", "end_date")

		doc.start_date = "2020-01-01"
		doc.end_date = "2020-12-31"
		doc.validate_from_to_dates("start_date", "end_date")

		doc.end_date = "2020-01-01"
		doc.start_date = "2020-12-31"
		self.assertRaises(
			frappe.exceptions.InvalidDates, doc.validate_from_to_dates, "start_date", "end_date"
		)

	def test_db_set_singles(self):
		c = frappe.get_doc("Contact Us Settings")
		key, val = "email_id", "admin1@example.com"
		c.db_set(key, val)
		changed_val = frappe.db.get_single_value(c.doctype, key)
		self.assertEqual(val, changed_val)

	def test_non_submittable_doctype_docstatus_transition(self):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "test submit guard"}).insert()
		doc.docstatus = 1

		self.assertRaises(frappe.DocstatusTransitionError, doc.save)

	def test_skip_docstatus_validation_flag(self):
		doc = frappe.get_doc({"doctype": "ToDo", "description": "test skip flag"}).insert()
		doc.docstatus = 1
		self.assertRaises(frappe.DocstatusTransitionError, doc.save)

		doc.reload()
		doc.docstatus = 1
		doc.flags.skip_docstatus_validation = True
		doc.save()
		self.assertEqual(frappe.db.get_value("ToDo", doc.name, "docstatus"), 1)

	def test_ignore_if_duplicate_on_a_unique_autoname_field(self):
		"""A doctype named after a unique field breaks two indexes with one row.

		`Role` is `autoname: field:role_name` and `role_name` is unique, so re-inserting the
		same role violates the primary key AND the unique index. Which one the backend reports
		is its own choice: MariaDB names PRIMARY, SQLite names the secondary index. Callers that
		seed idempotently pass `ignore_if_duplicate` and must not have to know the difference.
		"""
		role = frappe.get_doc(doctype="Role", role_name="_Test Duplicate Role").insert()
		self.addCleanup(role.delete)

		frappe.get_doc(doctype="Role", role_name="_Test Duplicate Role").insert(ignore_if_duplicate=True)
		self.assertEqual(frappe.db.count("Role", {"role_name": "_Test Duplicate Role"}), 1)

		# A skipped row has to leave the transaction usable. Postgres aborts it on any failed
		# statement, so a write here is what proves the row was skipped and not caught.
		role.db_set("disabled", 1)
		self.assertEqual(frappe.db.get_value("Role", role.name, "disabled"), 1)

		# Without the flag it is still an error, whichever index the backend blames. The
		# savepoint is for postgres: the failed insert aborts the transaction, so nothing
		# after this test could read or write without it.
		frappe.db.savepoint("test_ignore_if_duplicate")
		expected_error = (
			frappe.DuplicateEntryError
			if frappe.db.db_type == "sqlite"
			else (frappe.UniqueValidationError, frappe.DuplicateEntryError)
		)
		with self.assertRaises(expected_error):
			frappe.get_doc(doctype="Role", role_name="_Test Duplicate Role").insert()
		frappe.db.rollback(save_point="test_ignore_if_duplicate")

	def test_ignore_if_duplicate_on_a_unique_field_that_is_not_the_name(self):
		"""The clash can be on a unique index alone, with a name that is free.

		The row still has to be skipped, and the transaction still has to work afterwards.
		Postgres aborts a transaction on any failed statement, so there the row has to be
		skipped by the database rather than caught in python.
		"""
		doctype = new_doctype(unique=True).insert()
		self.addCleanup(doctype.delete, force=True)

		first = frappe.get_doc(doctype=doctype.name, some_fieldname="_Test Unique Value").insert()
		frappe.get_doc(doctype=doctype.name, some_fieldname="_Test Unique Value").insert(
			ignore_if_duplicate=True
		)
		self.assertEqual(frappe.db.count(doctype.name, {"some_fieldname": "_Test Unique Value"}), 1)

		# A write, not a read: this is what an aborted postgres transaction would fail on.
		first.db_set("some_fieldname", "_Test Unique Value 2")
		self.assertEqual(
			frappe.db.get_value(doctype.name, first.name, "some_fieldname"), "_Test Unique Value 2"
		)

	def test_sanitize_content_skips_json_fieldtype(self):
		"""JSON-fieldtype values must survive _sanitize_content untouched, even when
		they contain HTML-like substrings, while ordinary text fields on the same
		doctype are still sanitized."""
		from frappe.core.doctype.doctype.test_doctype import new_doctype

		if not frappe.db.exists("DocType", "Test JSON Sanitize"):
			new_doctype(
				"Test JSON Sanitize",
				fields=[
					{"label": "Config", "fieldname": "config", "fieldtype": "JSON"},
					{"label": "Description", "fieldname": "description", "fieldtype": "Text"},
				],
			).insert()

		payload = '{"label": "<b onclick=\\"alert(1)\\">hi</b>"}'
		doc = frappe.get_doc(
			{
				"doctype": "Test JSON Sanitize",
				"config": payload,
				"description": '<b onclick="alert(1)">hi</b>',
			}
		).insert()

		# JSON field: unchanged, still contains the raw onclick attribute
		self.assertEqual(doc.config, payload)

		# Text field: sanitized, onclick attribute stripped
		self.assertNotIn("onclick", doc.description)

	def test_base_document_alias(self):
		self.assertIs(BaseDocument, Document)

	def test_docstatus(self):
		doc = Document({"docstatus": 0, "doctype": "ToDo"})
		self.assertTrue(doc.docstatus.is_draft())
		self.assertEqual(doc.docstatus, 0)

		doc.docstatus = 1
		self.assertTrue(doc.docstatus.is_submitted())
		self.assertEqual(doc.docstatus, 1)

		doc.docstatus = 2
		self.assertTrue(doc.docstatus.is_cancelled())
		self.assertEqual(doc.docstatus, 2)

	def test_super_document_init_sets_values(self):
		class LegacyVirtualToDo(Document):
			def load_from_db(self):
				super(Document, self).__init__(
					{"doctype": "ToDo", "name": self.name, "description": "legacy"}
				)

		with self.assertWarns(FrappeDeprecationWarning):
			doc = LegacyVirtualToDo("ToDo", "legacy-todo")

		self.assertEqual(doc.name, "legacy-todo")
		self.assertEqual(doc.description, "legacy")

	def test_get_extended_class_with_no_extensions(self):
		"""Test that _get_extended_class returns the base class when no extensions are provided."""

		with self.patch_hooks({"extend_doctype_class": {}}):
			result = _get_extended_class(ToDo, "ToDo")
			self.assertEqual(result, ToDo)

		with self.patch_hooks({"extend_doctype_class": {"ToDo": []}}):
			result = _get_extended_class(ToDo, "ToDo")
			self.assertEqual(result, ToDo)

	def test_get_extended_class_with_extensions(self):
		"""Test that _get_extended_class properly combines extension classes with base class."""
		# Mock frappe.get_hooks to return extension paths
		extensions = [
			"frappe.tests.test_document.TestExtensionA",
			"frappe.tests.test_document.TestExtensionB",
		]

		with self.patch_hooks({"extend_doctype_class": {"ToDo": extensions}}):
			extended_class = _get_extended_class(ToDo, "ToDo")

			# Test that the extended class is different from base class
			self.assertNotEqual(extended_class, ToDo)

			# Test that the extended class has all methods from extensions and base
			instance = extended_class({"doctype": "ToDo"})
			self.assertTrue(hasattr(instance, "extension_method_a"))
			self.assertTrue(hasattr(instance, "extension_method_b"))

			# Test that methods work correctly
			self.assertEqual(instance.extension_method_a(), "method_a")
			self.assertEqual(instance.extension_method_b(), "method_b")

			# Test MRO (Method Resolution Order) - extensions should come first in reverse order
			mro_classes = [cls.__name__ for cls in extended_class.__mro__]
			self.assertIn("TestExtensionB", mro_classes)
			self.assertIn("TestExtensionA", mro_classes)
			self.assertIn("ToDo", mro_classes)

			# TestExtensionB should come before TestExtensionA (reverse order)
			idx_b = mro_classes.index("TestExtensionB")
			idx_a = mro_classes.index("TestExtensionA")
			idx_base = mro_classes.index("ToDo")
			self.assertLess(idx_b, idx_a)
			self.assertLess(idx_a, idx_base)

	def test_extension_overrides_todo_method(self):
		"""Test that an extension can override methods from the actual ToDo class"""
		from frappe.desk.doctype.todo.todo import ToDo

		# Mock the hooks to include our ToDo extension
		extensions = ["frappe.tests.test_document.TestToDoExtension"]

		with self.patch_hooks({"extend_doctype_class": {"ToDo": extensions}}):
			extended_class = _get_extended_class(ToDo, "ToDo")

			# Test that the extended class is different from base ToDo
			self.assertNotEqual(extended_class, ToDo)

			# Create an instance of the extended ToDo
			instance = extended_class({"doctype": "ToDo"})

			# Test that extension method is available
			self.assertTrue(hasattr(instance, "extension_method"))
			self.assertEqual(instance.extension_method(), "extension_method_called")

			# Test that the validate method is overridden
			# The extension's validate method should set custom_validation_called = True
			instance.validate()
			self.assertTrue(getattr(instance, "custom_validation_called", False))

			# Test MRO - extension should come before ToDo class
			mro_classes = [cls.__name__ for cls in extended_class.__mro__]
			self.assertIn("TestToDoExtension", mro_classes)
			self.assertIn("ToDo", mro_classes)

			# TestToDoExtension should come before ToDo
			idx_extension = mro_classes.index("TestToDoExtension")
			idx_todo = mro_classes.index("ToDo")
			self.assertLess(idx_extension, idx_todo)

	def test_extension_invalid_path_raises_exception(self):
		"""Test that an invalid extension path raises an appropriate exception"""
		from frappe.desk.doctype.todo.todo import ToDo

		# Mock the hooks to include an invalid extension path
		path_to_invalid_extension = "invalid.module.path.NonExistentClass"

		extensions = [
			"frappe.tests.test_document.TestExtensionA",  # valid
			path_to_invalid_extension,  # invalid
		]

		with self.patch_hooks({"extend_doctype_class": {"ToDo": extensions}}):
			# Test that ImportError is raised for invalid extension path
			with self.assertRaises(ImportError) as context:
				_get_extended_class(ToDo, "ToDo")

			# Check that the error message mentions the invalid path
			error_message = str(context.exception)
			self.assertIn(path_to_invalid_extension, error_message)

	def test_extended_class_is_pickleable(self):
		"""Test that extended class instances can be pickled and unpickled correctly"""
		from frappe.desk.doctype.todo.todo import ToDo

		# Mock the hooks to include extensions
		extensions = ["frappe.tests.test_document.TestToDoExtension"]

		with self.patch_hooks({"extend_doctype_class": {"ToDo": extensions}}):
			extended_class = _get_extended_class(ToDo, "ToDo")

			# Create an instance with some data
			original_instance = extended_class(
				{"doctype": "ToDo", "description": "Test ToDo for pickling", "status": "Open"}
			)

			# Set a custom attribute from extension
			original_instance.validate()  # This sets custom_validation_called = True
			original_instance.custom_attribute = "test_value"

			# Test that __getstate__ properly excludes unpicklable values
			state = original_instance.__getstate__()
			# These should be excluded by Document's __getstate__
			for unpicklable_key in ["meta", "permitted_fieldnames", "_weakref"]:
				self.assertNotIn(unpicklable_key, state)

			# Pickle the instance
			pickled_data = pickle.dumps(original_instance)

			# Clear the controller cache to ensure we're not using cached classes
			clear_todo_controller_cache()

			try:
				# Unpickle the instance (this should recreate the extended class)
				unpickled_instance = pickle.loads(pickled_data)
			finally:
				# Always clean up the controller cache to prevent test pollution
				clear_todo_controller_cache()

			# Test that the unpickled instance is of the extended class type
			self.assertEqual(unpickled_instance.__class__.__name__, f"Extended{ToDo.__name__}")

			# Test that the instance data is preserved
			self.assertEqual(unpickled_instance.doctype, "ToDo")
			self.assertEqual(unpickled_instance.description, "Test ToDo for pickling")
			self.assertEqual(unpickled_instance.status, "Open")
			self.assertEqual(unpickled_instance.custom_attribute, "test_value")
			self.assertTrue(getattr(unpickled_instance, "custom_validation_called", False))

			# Test that extension methods are still available
			self.assertTrue(hasattr(unpickled_instance, "extension_method"))
			self.assertEqual(unpickled_instance.extension_method(), "extension_method_called")

			# Test that original ToDo methods are still available
			self.assertTrue(hasattr(unpickled_instance, "on_update"))
			self.assertTrue(hasattr(unpickled_instance, "validate"))

	def test_get_valid_dict_json_field_with_list(self):
		"""Test that get_valid_dict properly handles and serializes JSON fields with list values."""
		from frappe import _dict

		doc = Document(
			{"doctype": "DocField", "fieldname": "test_json_field", "link_filters": [{"key": "val"}]}
		)
		meta = _dict(
			_fields={"link_filters": _dict(fieldname="link_filters", fieldtype="JSON", label="Link Filters")},
			get_valid_fields=lambda: ["link_filters"],
			get_table_fields=lambda **kwargs: (),
		)
		doc.meta = meta
		doc.flags = _dict()
		valid_dict = doc.get_valid_dict()
		self.assertEqual(valid_dict["link_filters"], '[{"key":"val"}]')

		# Non-JSON non-table fields should still reject list values
		doc_invalid = Document(
			{"doctype": "DocField", "label": "Invalid List", "description": ["item1", "item2"]}
		)
		doc_invalid.meta = _dict(
			_fields={
				"description": _dict(fieldname="description", fieldtype="Small Text", label="Description")
			},
			get_valid_fields=lambda: ["description"],
			get_table_fields=lambda **kwargs: (),
		)
		doc_invalid.flags = _dict()
		with self.assertRaises(frappe.ValidationError):
			doc_invalid.get_valid_dict()


class TestDocumentWebView(IntegrationTestCase):
	def get(self, path, user="Guest"):
		frappe.set_user(user)
		set_request(method="GET", path=path)
		make_form_dict(frappe.local.request)
		response = get_response()
		frappe.set_user("Administrator")
		return response

	def test_web_view_link_authentication(self):
		todo = frappe.get_doc({"doctype": "ToDo", "description": "Test"}).insert()
		document_key = todo.get_document_share_key()

		# with old-style signature key
		old_document_key = todo.get_signature()
		url = f"/ToDo/{todo.name}?key={old_document_key}"
		self.assertEqual(self.get(url).status, "403 FORBIDDEN")

		# with valid key
		url = f"/ToDo/{todo.name}?key={document_key}"
		self.assertEqual(self.get(url).status, "200 OK")

		# with invalid key
		invalid_key_url = f"/ToDo/{todo.name}?key=INVALID_KEY"
		self.assertEqual(self.get(invalid_key_url).status, "403 FORBIDDEN")

		# expire the key
		document_key_doc = frappe.get_doc("Document Share Key", {"key": document_key})
		document_key_doc.expires_on = "2020-01-01"
		document_key_doc.save(ignore_permissions=True)

		# with expired key
		self.assertEqual(self.get(url).status, "410 GONE")

		# without key
		url_without_key = f"/ToDo/{todo.name}"
		self.assertEqual(self.get(url_without_key).status, "403 FORBIDDEN")

		# Logged-in user can access the page without key
		self.assertEqual(self.get(url_without_key, "Administrator").status, "200 OK")

	def test_base_class_set_correctly_on_has_web_view_change(self):
		from pathlib import Path

		from frappe.modules.utils import get_doc_path, scrub

		frappe.flags.allow_doctype_export = True

		frappe.delete_doc_if_exists("DocType", "Test WebViewDocType", force=1)
		test_doctype = new_doctype(
			"Test WebViewDocType",
			custom=0,
			fields=[
				{"fieldname": "test_field", "fieldtype": "Data"},
				{"fieldname": "route", "fieldtype": "Data"},
				{"fieldname": "is_published", "fieldtype": "Check"},
			],
		)
		test_doctype.insert()

		doc_path = Path(get_doc_path(test_doctype.module, test_doctype.doctype, test_doctype.name))
		controller_file_path = doc_path / f"{scrub(test_doctype.name)}.py"

		# enable web view
		test_doctype.has_web_view = 1
		test_doctype.is_published_field = "is_published"
		test_doctype.save()

		# check if base class was updated to "WebsiteGenerator"
		with open(controller_file_path) as f:
			file_content = f.read()
			self.assertIn(
				"import WebsiteGenerator",
				file_content,
				"`WebsiteGenerator` not imported when web view is enabled!",
			)
			self.assertIn(
				"(WebsiteGenerator)",
				file_content,
				"`Document` class not replaced with `WebsiteGenerator` when web view is enabled!",
			)

		# disable web view
		test_doctype.has_web_view = 0
		test_doctype.save()

		# check if base class was updated to "Document" again
		with open(controller_file_path) as f:
			file_content = f.read()
			self.assertIn(
				"import Document", file_content, "`Document` not imported when web view is disabled!"
			)
			self.assertIn(
				"(Document)",
				file_content,
				"`WebsiteGenerator` class not replaced with `Document` when web view is disabled!",
			)

	def test_bulk_inserts(self):
		from frappe.model.document import bulk_insert

		doctype = "Role Profile"
		child_field = "roles"
		child_doctype = frappe.get_meta(doctype).get_field(child_field).options

		sent_docs = set()
		sent_child_docs = set()

		def doc_generator():
			for _ in range(21):
				doc = frappe.new_doc(doctype)
				doc.role_profile = frappe.generate_hash()
				doc.append("roles", {"role": "System Manager"})

				doc.set_new_name()
				doc.set_parent_in_children()

				sent_docs.add(doc.name)
				sent_child_docs.add(doc.roles[0].name)

				yield doc

		bulk_insert(doctype, doc_generator(), chunk_size=5)

		all_docs = set(frappe.get_all(doctype, pluck="name"))
		all_child_docs = set(
			frappe.get_all(
				child_doctype, filters={"parenttype": doctype, "parentfield": child_field}, pluck="name"
			)
		)
		self.assertEqual(sent_docs - all_docs, set(), "All docs should be inserted")
		self.assertEqual(sent_child_docs - all_child_docs, set(), "All child docs should be inserted")


class TestLazyDocument(IntegrationTestCase):
	def test_lazy_documents(self):
		# Warmup meta etc
		_ = frappe.get_lazy_doc("User", "Guest")
		eager_guest: User = frappe.get_doc("User", "Guest")

		# Only one query for parent document
		with self.assertQueryCount(1):
			guest: User = frappe.get_lazy_doc("User", "Guest")
			self.assertEqual(guest.user_type, "Website User")

		# Only one query for one table access
		with self.assertQueryCount(1):
			guest_role = guest.roles[0]
			self.assertEqual(guest_role.role, "Guest")
			self.assertIsInstance(guest_role, type(eager_guest.roles[0]))

		# Only one query for one table access
		with self.assertQueryCount(1):
			_ = guest.role_profiles

		# No queries for repeat access, same object
		with self.assertQueryCount(0):
			guest_role_repeat_access = guest.roles[0]
		self.assertIs(guest_role, guest_role_repeat_access)

		# Same object after first access
		with self.assertQueryCount(0):
			self.assertIs(guest.roles, guest.get("roles"))

		# things accessing __dict__ by default should be updated too
		self.assertTrue(frappe.get_lazy_doc("User", "Guest").get("roles"))

	def test_lazy_single_document(self):
		_ = frappe.get_lazy_doc("Navbar Settings", "Navbar Settings")

		with self.assertQueryCount(1):
			frappe.get_lazy_doc("Navbar Settings", "Navbar Settings")

	def test_lazy_doc_efficient_saves(self):
		# Only touched tables and self should be updated.
		per_update = 1

		guest = frappe.get_lazy_doc("User", "Guest")
		with self.assertQueryCount(per_update):
			guest.db_update_all()

		guest = frappe.get_lazy_doc("User", "Guest")
		_ = guest.roles
		with self.assertQueryCount(per_update * (1 + len(guest.roles))):
			guest.db_update_all()

		# Save should works, it won't be efficient because internal code will just trigger fetching
		# of child tables to resave them.
		guest.save()

	def test_lazy_magic(self):
		self.assertIsNone(getattr(LazyChildTable, "__set__", None))

		guest = frappe.get_lazy_doc("User", "Guest")
		# table fields will be populated on first access
		self.assertIsNone(guest.__dict__.get("roles"))
		roles = guest.roles
		self.assertIs(guest.__dict__.get("roles"), roles)

		# Allow overriding from user code
		roles_copy = deepcopy(roles)
		guest.roles = roles_copy
		self.assertIs(guest.__dict__.get("roles"), roles_copy)

		with patch(f"{LazyChildTable.__module__}.{LazyChildTable.__name__}.__get__") as getter:
			_ = guest.roles
			self.assertFalse(getter.called)

		guest = frappe.get_lazy_doc("User", "Guest")
		with patch(f"{LazyChildTable.__module__}.{LazyChildTable.__name__}.__get__") as getter:
			_ = guest.roles
			self.assertTrue(getter.called)

		# Ensure same method signature
		eager_guest: User = frappe.get_doc("User", "Guest")
		original_class = eager_guest.__class__
		lazy_class = guest.__class__

		def compare_signatures(a, b, attr):
			a_sig = inspect.signature(getattr(a, attr)).parameters
			b_sig = inspect.signature(getattr(b, attr)).parameters

			for (param_a, value_a), (param_b, value_b) in zip(a_sig.items(), b_sig.items(), strict=True):
				self.assertEqual(param_a, param_b)
				self.assertEqual(value_a.default, value_b.default)

		for method in ("append", "extend", "db_update_all", "get"):
			compare_signatures(original_class, lazy_class, method)

	def test_append_extend_update(self):
		guest = frappe.get_lazy_doc("User", "Guest")
		_ = guest.append("roles")
		self.assertEqual(len(guest.roles), 2)

		guest = frappe.get_lazy_doc("User", "Guest")
		_ = guest.extend("roles", [{}])
		self.assertEqual(len(guest.roles), 2)

		guest = frappe.get_lazy_doc("User", "Guest")
		_ = guest.update({"roles": [{"role": "Administrator"}]})
		self.assertEqual(len(guest.roles), 1)
		self.assertEqual(guest.roles[0].role, "Administrator")

		guest = frappe.get_lazy_doc("User", "Guest")
		_ = guest.set("roles", [{"role": "Administrator"}])
		self.assertEqual(len(guest.roles), 1)
		self.assertEqual(guest.roles[0].role, "Administrator")

	def test_for_update(self):
		guest = frappe.get_lazy_doc("User", "Guest", for_update=True)
		self.assertTrue(guest.flags.for_update)

	def test_pickling(self):
		guest = frappe.get_lazy_doc("User", "Guest")
		unpickled = pickle.loads(pickle.dumps(guest))
		self.assertIsInstance(unpickled, LazyDocument)
		self.assertIs(type(unpickled), type(guest))
		self.assertEqual(unpickled.name, "Guest")
		# unloaded child tables stay lazy and still load after unpickling
		self.assertNotIn("roles", unpickled.__dict__)
		self.assertTrue(unpickled.get("roles"))

		# loaded child tables survive the round trip without a refetch
		guest = frappe.get_lazy_doc("User", "Guest")
		roles = [r.role for r in guest.roles]
		unpickled = pickle.loads(pickle.dumps(guest))
		self.assertIn("roles", unpickled.__dict__)
		self.assertEqual([r.role for r in unpickled.roles], roles)

		# reconstruction works even when the lazy controller cache is cold,
		# e.g. unpickling in a freshly started worker
		data = pickle.dumps(frappe.get_lazy_doc("User", "Guest"))
		frappe.lazy_controllers.pop(frappe.local.site, None)
		unpickled = pickle.loads(data)
		self.assertIsInstance(unpickled, LazyDocument)
		self.assertTrue(unpickled.get("roles"))


class TestGetDocs(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		cls.child_dt = "Test Get Docs Child"
		cls.parent_dt = "Test Get Docs Parent"

		cls.child_dt = new_doctype(istable=1).insert().name
		cls.parent_dt = (
			new_doctype(
				fields=[
					{"fieldtype": "Data", "fieldname": "title", "label": "Title"},
					{
						"fieldtype": "Table",
						"fieldname": "child_table",
						"options": cls.child_dt,
						"label": "Child Table",
					},
				],
			)
			.insert()
			.name
		)
		for i in range(5):
			frappe.get_doc(
				{
					"doctype": cls.parent_dt,
					"title": f"Record {i}",
					"child_table": [
						{"some_fieldname": f"child_{i}_0"},
						{"some_fieldname": f"child_{i}_1"},
					],
				}
			).insert()

	@classmethod
	def tearDownClass(cls):
		frappe.db.delete(cls.child_dt)
		frappe.db.delete(cls.parent_dt)
		frappe.delete_doc("DocType", cls.parent_dt, force=True)
		frappe.delete_doc("DocType", cls.child_dt, force=True)
		super().tearDownClass()

	def test_returns_document_instances(self):
		docs = frappe.get_docs(self.parent_dt)
		self.assertEqual(len(docs), 5)
		self.assertIsInstance(docs[0], frappe.model.document.Document)
		self.assertEqual(docs[0].doctype, self.parent_dt)

	def test_child_tables_populated(self):
		docs = frappe.get_docs(self.parent_dt)
		for doc in docs:
			self.assertEqual(len(doc.child_table), 2)
			for child in doc.child_table:
				self.assertIsInstance(child, frappe.model.document.Document)
				self.assertEqual(child.doctype, self.child_dt)

	def test_parity_with_get_doc(self):
		docs = frappe.get_docs(self.parent_dt, limit=1)
		doc_bulk = docs[0]
		doc_single = frappe.get_doc(self.parent_dt, doc_bulk.name)

		self.assertEqual(doc_bulk.as_dict(), doc_single.as_dict())

	def test_filters(self):
		docs = frappe.get_docs(self.parent_dt, filters={"title": "Record 0"})
		self.assertEqual(len(docs), 1)
		self.assertEqual(docs[0].title, "Record 0")

	def test_limit(self):
		docs = frappe.get_docs(self.parent_dt, limit=2)
		self.assertEqual(len(docs), 2)

	def test_limit_start(self):
		all_docs = frappe.get_docs(self.parent_dt, order_by="creation asc")
		offset_docs = frappe.get_docs(self.parent_dt, limit_start=2, limit=5, order_by="creation asc")
		self.assertEqual(len(offset_docs), 3)
		self.assertEqual(offset_docs[0].name, all_docs[2].name)

	def test_order_by(self):
		docs_asc = frappe.get_docs(self.parent_dt, order_by="creation asc")
		docs_desc = frappe.get_docs(self.parent_dt, order_by="creation desc")
		self.assertEqual(docs_asc[0].name, docs_desc[-1].name)

	def test_generator_parity(self):
		eager = frappe.get_docs(self.parent_dt, order_by="creation asc")
		gen_docs = list(
			frappe.get_docs(self.parent_dt, as_iterator=True, chunk_size=2, order_by="creation asc")
		)
		self.assertEqual([d.name for d in eager], [d.name for d in gen_docs])

	def test_for_update_sets_flag(self):
		docs = frappe.get_docs(self.parent_dt, limit=1, for_update=True)
		self.assertTrue(docs[0].flags.for_update)


class TestDocsCollection(IntegrationTestCase):
	"""Tests for the `DocsCollection` descriptor on `Document` subclasses.

	The descriptor exposes typed, doctype-scoped helpers (`.docs.get`,
	`.docs.last`, `.docs.filter`, `.docs.new`, `.docs.delete`) on any
	controller class that declares `_DOCTYPE_NAME`.
	"""

	def tearDown(self):
		frappe.db.rollback()
		return super().tearDown()

	def test_doctype_resolved_from_controller(self):
		self.assertEqual(ToDo.docs._doctype, "ToDo")

	def test_get_returns_document(self):
		todo = ToDo.docs.new(description="docs.get test").insert()
		fetched = ToDo.docs.get(todo.name)
		self.assertIsInstance(fetched, ToDo)
		self.assertEqual(fetched.name, todo.name)
		self.assertEqual(fetched.description, "docs.get test")

	def test_get_cached(self):
		todo = ToDo.docs.new(description="docs.get cached").insert()
		cached = ToDo.docs.get(todo.name, cached=True)
		self.assertEqual(cached.name, todo.name)
		# Second call should return the same cached object.
		cached2 = ToDo.docs.get(todo.name, cached=True)
		self.assertIs(cached, cached2)

	def test_get_lazy(self):
		todo = ToDo.docs.new(description="docs.get lazy").insert()
		lazy = ToDo.docs.get(todo.name, lazy=True)
		self.assertEqual(lazy.name, todo.name)

	def test_get_cached_and_lazy_are_exclusive(self):
		with self.assertRaises(ValueError):
			ToDo.docs.get("dummy", cached=True, lazy=True)

	def test_new_creates_unsaved_document(self):
		todo = ToDo.docs.new(description="docs.new test")
		self.assertIsInstance(todo, ToDo)
		self.assertEqual(todo.doctype, "ToDo")
		self.assertEqual(todo.description, "docs.new test")
		self.assertTrue(todo.get("__islocal"))

	def test_last_returns_most_recent(self):
		marker = f"docs.last marker {frappe.generate_hash(length=8)}"
		_ = ToDo.docs.new(description=marker).insert()
		second = ToDo.docs.new(description=marker).insert()
		last = ToDo.docs.last({"description": marker})
		self.assertEqual(last.name, second.name)

	def test_filter_returns_matching_documents(self):
		marker = f"docs.filter marker {frappe.generate_hash(length=8)}"
		created = [ToDo.docs.new(description=marker).insert() for _ in range(3)]
		docs = ToDo.docs.filter({"description": marker})
		self.assertEqual(len(docs), 3)
		names = {d.name for d in docs}
		self.assertEqual(names, {d.name for d in created})
		self.assertTrue(all(isinstance(d, ToDo) for d in docs))

	def test_subclass_uses_its_own_doctype(self):
		"""Subclasses with their own `_DOCTYPE_NAME` resolve independently."""
		self.assertEqual(ToDo.docs._doctype, "ToDo")
		self.assertEqual(Note.docs._doctype, "Note")

	def test_missing_doctype_name_raises(self):
		class Orphan(Document):
			pass

		with self.assertRaises(AttributeError):
			Orphan.docs._doctype

	def test_not_accessible_via_instances(self):
		todo = ToDo.docs.new(description="docs instance access")
		with self.assertRaises(AttributeError):
			todo.docs


def clear_todo_controller_cache():
	"""Helper method to clear controller cache for ToDo"""
	if hasattr(frappe, "controllers") and frappe.local.site in frappe.controllers:
		frappe.controllers[frappe.local.site].pop("ToDo", None)
