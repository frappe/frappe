# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE

import json
from unittest.mock import patch
from uuid import uuid4

import frappe
from frappe.core.doctype.attachment_queue.attachment_queue import queued_file
from frappe.core.doctype.attachment_queue.extraction import (
	QUEUE_DOCTYPE,
	coerce,
	coerce_values,
	extraction_complete,
	field_schema,
	read_now,
	readable_error,
)
from frappe.core.doctype.attachment_queue.test_attachment_queue import minimal_pdf
from frappe.tests import IntegrationTestCase
from frappe.utils.file_manager import save_file

TARGET_DOCTYPE = "ToDo"


def set_target(test, **settings):
	"""Set `settings` on the target DocType for the length of `test`."""
	original = frappe.db.get_value("DocType", TARGET_DOCTYPE, list(settings), as_dict=True)
	frappe.db.set_value("DocType", TARGET_DOCTYPE, settings)
	frappe.clear_cache(doctype=TARGET_DOCTYPE)
	test.addCleanup(restore_target, original)


def restore_target(original):
	# A schema change inside a test commits, so putting this back has to commit too.
	# Rolling back first keeps that commit from carrying the test's own rows with it.
	frappe.db.rollback()
	frappe.db.set_value("DocType", TARGET_DOCTYPE, original)
	frappe.db.commit()  # nosemgrep
	frappe.clear_cache(doctype=TARGET_DOCTYPE)


def make_entry(**fields):
	return frappe.get_doc(
		{
			"doctype": QUEUE_DOCTYPE,
			"document_type": TARGET_DOCTYPE,
			"source_file": "/private/files/not-read.pdf",
			**fields,
		}
	).insert()


class TestFieldSchema(IntegrationTestCase):
	"""What the agent is told it may fill in."""

	def test_offers_the_fields_a_file_can_state_a_value_for(self):
		offered = {field["fieldname"]: field for field in field_schema(TARGET_DOCTYPE)}

		self.assertTrue(offered["description"]["required"])
		self.assertEqual(offered["priority"]["fieldtype"], "Select")
		self.assertEqual(offered["priority"]["options"], ["High", "Medium", "Low"])
		self.assertEqual(offered["allocated_to"]["links_to"], "User")

	def test_leaves_out_fields_no_file_can_fill(self):
		offered = {field["fieldname"] for field in field_schema(TARGET_DOCTYPE)}

		# a layout field holds no value, and these three are not the file's to state
		self.assertNotIn("description_section", offered)
		self.assertNotIn("assigned_by_full_name", offered)  # Read Only
		self.assertNotIn("assignment_rule", offered)  # read_only
		self.assertNotIn("color", offered)  # Color


class TestCoerceValues(IntegrationTestCase):
	"""The contract boundary: what the model sends, against what the DocType can hold."""

	def coerce(self, values):
		return coerce_values(TARGET_DOCTYPE, values)

	def test_keeps_a_value_each_field_can_hold(self):
		kept, skipped = self.coerce({"description": "Invoice 42", "priority": "High", "date": "2026-03-04"})

		self.assertEqual(kept, {"description": "Invoice 42", "priority": "High", "date": "2026-03-04"})
		self.assertEqual(skipped, {})

	def test_reports_a_fieldname_the_doctype_does_not_have(self):
		kept, skipped = self.coerce({"no_such_field": "x", "description": "kept"})

		self.assertEqual(kept, {"description": "kept"})
		self.assertEqual(skipped["no_such_field"]["value"], "x")
		self.assertIn("no such field", skipped["no_such_field"]["reason"])

	def test_reports_a_select_option_that_does_not_exist(self):
		kept, skipped = self.coerce({"priority": "Extremely Urgent"})

		self.assertEqual(kept, {})
		self.assertEqual(skipped["priority"]["value"], "Extremely Urgent")
		self.assertIn("option", skipped["priority"]["reason"])

	def test_reports_a_link_to_a_record_that_does_not_exist(self):
		"""The case the reader can act on: the file names a record the site does not have."""
		kept, skipped = self.coerce({"allocated_to": "nobody@example.com"})

		self.assertEqual(kept, {})
		self.assertEqual(skipped["allocated_to"]["value"], "nobody@example.com")
		self.assertIn("User", skipped["allocated_to"]["reason"])

	def test_reports_a_date_the_field_cannot_read(self):
		kept, skipped = self.coerce({"date": "sometime next spring"})

		self.assertEqual(kept, {})
		self.assertIn("date", skipped["date"]["reason"])

	def test_reads_a_date_the_model_wrote_in_another_format(self):
		kept, _skipped = self.coerce({"date": "04-03-2026"})

		self.assertEqual(kept["date"], "2026-03-04")

	def test_says_nothing_about_a_field_the_file_left_blank(self):
		# nothing to fill in and nothing for the reader to do about it
		kept, skipped = self.coerce({"description": "   ", "priority": None})

		self.assertEqual(kept, {})
		self.assertEqual(skipped, {})

	def test_reports_a_read_only_field_the_model_offered_anyway(self):
		kept, skipped = self.coerce({"assignment_rule": "anything"})

		self.assertEqual(kept, {})
		self.assertIn("assignment_rule", skipped)

	def test_carries_a_label_so_the_reader_recognises_the_field(self):
		_kept, skipped = self.coerce({"allocated_to": "nobody@example.com"})

		self.assertEqual(skipped["allocated_to"]["label"], "Allocated To")


class TestCoerce(IntegrationTestCase):
	"""Fieldtypes ToDo has none of, against a field that is only its type here."""

	def coerce(self, fieldtype, value, **df):
		return coerce(frappe._dict(fieldtype=fieldtype, **df), value)

	def test_reads_an_amount_written_with_separators(self):
		self.assertEqual(self.coerce("Currency", "1,234.50"), 1234.50)
		self.assertEqual(self.coerce("Currency", 980), 980.0)
		self.assertEqual(self.coerce("Int", "42"), 42)

	def test_turns_away_an_amount_that_is_not_a_number(self):
		# read as zero, this would show on the form as an amount the file never stated
		self.assertIsNone(self.coerce("Currency", "see attached"))
		self.assertIsNone(self.coerce("Float", "N/A"))
		self.assertIsNone(self.coerce("Int", True))

	def test_reads_a_check_either_way_round(self):
		self.assertEqual(self.coerce("Check", "Yes"), 1)
		self.assertEqual(self.coerce("Check", "no"), 0)
		self.assertIsNone(self.coerce("Check", "probably"))

	def test_reads_a_datetime_and_a_time(self):
		self.assertEqual(self.coerce("Datetime", "2026-03-04 09:30:00"), "2026-03-04 09:30:00")
		self.assertEqual(self.coerce("Time", "09:30:00"), "9:30:00")
		self.assertIsNone(self.coerce("Datetime", "whenever"))


class TestReadableError(IntegrationTestCase):
	"""What the person filling in the document is shown when the file could not be read."""

	def test_pulls_the_service_message_out_of_the_wrappers(self):
		raw = (
			"ProviderError: anthropic invalid request error (HTTP 400): "
			"litellm.BadRequestError: AnthropicException - "
			'b\'{"type":"error","error":{"type":"invalid_request_error","message":'
			'"Your credit balance is too low to access the Anthropic API."},'
			'"request_id":"req_011Cgf"}\''
		)

		self.assertEqual(readable_error(raw), "Your credit balance is too low to access the Anthropic API.")

	def test_keeps_a_json_escape_readable(self):
		self.assertEqual(readable_error(r'{"message":"Model \"x\" is unknown."}'), 'Model "x" is unknown.')

	def test_falls_back_to_the_first_line(self):
		self.assertEqual(
			readable_error("The flow server stopped.\nTraceback (most recent call last):"),
			"The flow server stopped.",
		)

	def test_says_so_when_there_is_no_reason(self):
		for empty in (None, "", "   "):
			self.assertEqual(readable_error(empty), "Flow did not say why.")


class TestReadNow(IntegrationTestCase):
	"""Reading a file the review opens, whatever happened to it before."""

	def setUp(self):
		set_target(self, enable_upload_first_workflow=1, enable_flow_extraction=1)
		# the worker is never reached: these tests are about which entries are offered to it
		self.enqueue = self.enterContext(patch("frappe.enqueue"))

	def test_an_uploaded_entry_keeps_its_file_for_the_worker(self):
		with self.set_user("test@example.com"):
			unique = uuid4().hex[:8]
			file_doc = save_file(f"{unique}.pdf", minimal_pdf(unique), None, None, is_private=1)
			entry = make_entry(source_file=file_doc.file_url)

			self.assertEqual(entry.extraction_status, "Started")
			self.assertEqual(queued_file(entry), file_doc.name)
			self.enqueue.assert_called_once()

	def test_reads_an_entry_that_was_never_offered_to_flow(self):
		# an entry uploaded before its DocType asked for extraction
		entry = make_entry()
		entry.db_set({"extraction_status": None}, update_modified=False)
		self.enqueue.reset_mock()

		self.assertEqual(read_now(entry.name), "Started")
		entry.reload()

		self.assertEqual(entry.extraction_status, "Started")
		self.enqueue.assert_called_once()

	def test_reads_an_entry_whose_read_failed(self):
		entry = make_entry()
		entry.db_set({"extraction_status": "Failed", "extraction_error": "no credit"}, update_modified=False)
		self.enqueue.reset_mock()

		self.assertEqual(read_now(entry.name), "Started")
		entry.reload()

		self.assertEqual(entry.extraction_status, "Started")
		self.assertIsNone(entry.extraction_error)
		self.enqueue.assert_called_once()

	def test_leaves_an_entry_that_is_already_read_or_being_read(self):
		for status in ("Started", "Completed"):
			with self.subTest(status=status):
				entry = make_entry()
				entry.db_set({"extraction_status": status}, update_modified=False)
				self.enqueue.reset_mock()

				self.assertEqual(read_now(entry.name), status)
				self.enqueue.assert_not_called()

	def test_reads_nothing_when_the_doctype_does_not_ask_for_it(self):
		entry = make_entry()
		entry.db_set({"extraction_status": None}, update_modified=False)
		frappe.db.set_value("DocType", TARGET_DOCTYPE, "enable_flow_extraction", 0)
		frappe.clear_cache(doctype=TARGET_DOCTYPE)
		self.enqueue.reset_mock()

		self.assertEqual(read_now(entry.name), "")
		self.enqueue.assert_not_called()


class TestExtractionComplete(IntegrationTestCase):
	"""The three statuses an entry moves through."""

	def setUp(self):
		set_target(self, enable_upload_first_workflow=1)

		# Extraction stays off, so inserting the entry does not queue a worker: these tests
		# are about what the run's outcome does to the entry, not about reading a file.
		self.entry = make_entry()
		self.entry.db_set("extraction_status", "Started", update_modified=False)

	def run_for(self, status, error=None):
		return frappe._dict(
			reference_doctype=QUEUE_DOCTYPE,
			reference_name=self.entry.name,
			status=status,
			error=error,
		)

	def test_a_run_that_reported_values_completes_the_entry(self):
		self.entry.db_set("extracted_values", json.dumps({"description": "Invoice 42"}))

		extraction_complete(self.run_for("Completed"))
		self.entry.reload()

		self.assertEqual(self.entry.extraction_status, "Completed")
		self.assertIsNone(self.entry.extraction_error)

	def test_a_run_that_reported_nothing_fails_the_entry(self):
		extraction_complete(self.run_for("Completed"))
		self.entry.reload()

		self.assertEqual(self.entry.extraction_status, "Failed")
		self.assertIn("did not report", self.entry.extraction_error)

	def test_a_failed_run_carries_its_error_to_the_entry(self):
		extraction_complete(self.run_for("Failed", error="the model is unreachable"))
		self.entry.reload()

		self.assertEqual(self.entry.extraction_status, "Failed")
		self.assertEqual(self.entry.extraction_error, "the model is unreachable")

	def test_a_run_for_anything_else_is_not_an_extraction(self):
		extraction_complete(frappe._dict(reference_doctype="ToDo", reference_name="x", status="Completed"))
		self.entry.reload()

		self.assertEqual(self.entry.extraction_status, "Started")
