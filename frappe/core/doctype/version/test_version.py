# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import copy

import frappe
from frappe.core.doctype.version.version import (
	_as_string,
	_generate_html_diff,
	_should_generate_html_diff,
	get_diff,
)
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.tests.utils import make_test_objects


class TestHTMLDiff(UnitTestCase):
	def test_generate_html_diff_produces_table(self):
		"""Test HTML diff generates a table with content."""
		result = _generate_html_diff("line1\nline2", "line1\nmodified")

		self.assertIsNotNone(result)
		self.assertIn("<table", result)
		self.assertIn("line1", result)

	def test_generate_html_diff_escapes_html(self):
		"""Test HTML output is properly escaped and safe."""
		old_value = "<script>alert('xss')</script>\nline2"
		new_value = "<div>injected</div>\nline2"

		result = _generate_html_diff(old_value, new_value)

		self.assertIsNotNone(result)
		# Raw script/div tags should be escaped, not executable
		self.assertNotIn("<script>alert", result)
		self.assertNotIn("<div>injected", result)
		# Escaped versions should be present
		self.assertIn("&lt;script&gt;", result)
		self.assertIn("&lt;div&gt;", result)

	def test_should_generate_html_diff_multiline(self):
		"""Test should_generate_html_diff returns True for multiline text."""
		self.assertTrue(_should_generate_html_diff("line1\nline2", "line1\nmodified"))
		self.assertTrue(_should_generate_html_diff("single", "multi\nline"))
		self.assertTrue(_should_generate_html_diff("multi\nline", "single"))

	def test_should_generate_html_diff_long_text(self):
		"""Test should_generate_html_diff returns True for text > 80 characters."""
		self.assertTrue(_should_generate_html_diff("a" * 81, "b"))
		self.assertTrue(_should_generate_html_diff("a", "b" * 81))
		self.assertTrue(_should_generate_html_diff("a" * 81, "b" * 81))

	def test_should_generate_html_diff_short_text(self):
		"""Test should_generate_html_diff returns False for short single-line text."""
		self.assertFalse(_should_generate_html_diff("short", "text"))
		self.assertFalse(_should_generate_html_diff("a" * 80, "b" * 80))  # Exactly 80 chars

	def test_should_generate_html_diff_empty_values(self):
		"""Test should_generate_html_diff returns False when either value is empty."""
		self.assertFalse(_should_generate_html_diff("", "short"))
		self.assertFalse(_should_generate_html_diff("short", ""))
		self.assertFalse(_should_generate_html_diff("", ""))
		# Even long/multiline text returns False if the other value is empty
		self.assertFalse(_should_generate_html_diff("", "a" * 81))
		self.assertFalse(_should_generate_html_diff("multi\nline", ""))

	def test_as_string_converts_values(self):
		"""Test _as_string converts values to strings correctly."""
		self.assertEqual(_as_string("text"), "text")
		self.assertEqual(_as_string(None), "")
		self.assertEqual(_as_string(""), "")
		self.assertEqual(_as_string(0), "0")


class TestVersion(IntegrationTestCase):
	def test_onload_generates_html_diffs_for_multiline(self):
		"""Test onload generates HTML diffs for multiline changes."""
		version = frappe.get_doc(
			doctype="Version",
			ref_doctype="ToDo",
			docname="test-doc",
			data=frappe.as_json({"changed": [["description", "line1\nline2", "line1\nmodified"]]}),
		)

		version.onload()

		html_diffs = version.get_onload().get("html_diffs")
		self.assertIsNotNone(html_diffs)
		self.assertIn("description", html_diffs)
		self.assertIn("<table", html_diffs["description"])

	def test_onload_generates_html_diffs_for_long_text(self):
		"""Test onload generates HTML diffs for text > 80 characters."""
		version = frappe.get_doc(
			doctype="Version",
			ref_doctype="ToDo",
			docname="test-doc",
			data=frappe.as_json({"changed": [["notes", "x" * 81, "y" * 81]]}),
		)

		version.onload()

		html_diffs = version.get_onload().get("html_diffs")
		self.assertIsNotNone(html_diffs)
		self.assertIn("notes", html_diffs)

	def test_onload_no_html_diffs_for_simple_changes(self):
		"""Test onload doesn't generate HTML diffs for simple short changes."""
		version = frappe.get_doc(
			doctype="Version",
			ref_doctype="ToDo",
			docname="test-doc",
			data=frappe.as_json({"changed": [["status", "Open", "Closed"]]}),
		)

		version.onload()

		html_diffs = version.get_onload().get("html_diffs")
		self.assertIsNone(html_diffs)

	def test_onload_handles_empty_data(self):
		"""Test onload handles empty or missing data gracefully."""
		version = frappe.get_doc(
			doctype="Version",
			ref_doctype="ToDo",
			docname="test-doc",
			data=None,
		)

		# Should not raise an error
		version.onload()
		self.assertIsNone(version.get_onload().get("html_diffs"))

		version.data = frappe.as_json({"changed": []})
		version.onload()
		self.assertIsNone(version.get_onload().get("html_diffs"))

	def test_get_diff(self):
		frappe.set_user("Administrator")
		test_records = make_test_objects("Event", reset=True)
		old_doc = frappe.get_doc("Event", test_records[0])
		new_doc = copy.deepcopy(old_doc)

		old_doc.color = None
		new_doc.color = "#fafafa"

		diff = get_diff(old_doc, new_doc)["changed"]

		self.assertEqual(get_fieldnames(diff)[0], "color")
		self.assertTrue(get_old_values(diff)[0] is None)
		self.assertEqual(get_new_values(diff)[0], "#fafafa")

		new_doc.starts_on = "2017-07-20"

		diff = get_diff(old_doc, new_doc)["changed"]

		self.assertEqual(get_fieldnames(diff)[1], "starts_on")
		self.assertEqual(get_old_values(diff)[1], "01-01-2014 00:00:00")
		self.assertEqual(get_new_values(diff)[1], "07-20-2017 00:00:00")

	def set_ignore_versioning(self, meta, fieldname):
		"""Turn on ignore_versioning for a field and drop the cached set built from it."""
		df = meta.get_field(fieldname)
		df.ignore_versioning = 1
		meta.__dict__.pop("ignore_versioning_fields", None)

		self.addCleanup(meta.__dict__.pop, "ignore_versioning_fields", None)
		self.addCleanup(setattr, df, "ignore_versioning", 0)

	def test_get_diff_skips_ignore_versioning_field(self):
		"""Test fields with ignore_versioning are left out of the diff."""
		frappe.set_user("Administrator")
		test_records = make_test_objects("Event", reset=True)
		old_doc = frappe.get_doc("Event", test_records[0])
		new_doc = copy.deepcopy(old_doc)

		self.set_ignore_versioning(new_doc.meta, "color")

		old_doc.color = None
		new_doc.color = "#fafafa"

		# the flag is opt-in, so every other caller of get_diff still sees color
		self.assertIn("color", get_fieldnames(get_diff(old_doc, new_doc)["changed"]))

		# color is the only change and it is ignored, so there is no Version to save
		self.assertIsNone(get_diff(old_doc, new_doc, include_ignored_fields=False))

		new_doc.subject = "changed subject"
		diff = get_diff(old_doc, new_doc, include_ignored_fields=False)["changed"]

		# subject is versioned as usual, color is left out
		self.assertNotIn("color", get_fieldnames(diff))
		self.assertIn("subject", get_fieldnames(diff))

	def test_get_diff_skips_ignore_versioning_field_in_child_rows(self):
		"""Test ignored fields are left out of added and removed child rows."""
		frappe.set_user("Administrator")
		test_records = make_test_objects("Event", reset=True)
		doc_without_row = frappe.get_doc("Event", test_records[0])
		doc_with_row = copy.deepcopy(doc_without_row)

		self.set_ignore_versioning(frappe.get_meta("Event Participants"), "email")

		# unsaved row has no name, so get_diff cannot match it against an old row
		doc_with_row.append(
			"event_participants",
			{
				"reference_doctype": "Contact",
				"reference_docname": "_Test Contact",
				"email": "a@example.com",
			},
		)

		# get_diff(old, new): row is only in new, so it is reported as added.
		# every entry is [table_fieldname, row_data], so [0] is the first entry and [1] its row data
		added_row = get_diff(doc_without_row, doc_with_row, include_ignored_fields=False)["added"][0][1]

		# arguments flipped: row is only in old now, so the same row is reported as removed
		removed_row = get_diff(doc_with_row, doc_without_row, include_ignored_fields=False)["removed"][0][1]

		# email is dropped from the row data, the other fields are kept
		self.assertNotIn("email", added_row)
		self.assertIn("reference_doctype", added_row)
		self.assertNotIn("email", removed_row)
		self.assertIn("reference_doctype", removed_row)

		# the flag is opt-in, so the row data is untouched by default
		self.assertIn("email", get_diff(doc_without_row, doc_with_row)["added"][0][1])

	def test_no_version_on_new_doc(self):
		from frappe.desk.form.load import get_versions

		t = frappe.get_doc(doctype="ToDo", description="something")
		t.save(ignore_version=False)

		self.assertFalse(get_versions(t))

		t = frappe.get_doc(t.doctype, t.name)
		t.description = "changed"
		t.save(ignore_version=False)
		self.assertTrue(get_versions(t))


def get_fieldnames(change_array):
	return [d[0] for d in change_array]


def get_old_values(change_array):
	return [d[1] for d in change_array]


def get_new_values(change_array):
	return [d[2] for d in change_array]
