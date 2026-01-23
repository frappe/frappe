# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import copy

import frappe
from frappe.core.doctype.version.version import get_diff
from frappe.test_runner import make_test_objects
from frappe.tests.utils import FrappeTestCase


class TestVersion(FrappeTestCase):
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

		html_diffs = (version.get_onload() or frappe._dict()).get("html_diffs")
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
		self.assertIsNone((version.get_onload() or frappe._dict()).get("html_diffs"))

		version.data = frappe.as_json({"changed": []})
		version.onload()
		self.assertIsNone((version.get_onload() or frappe._dict()).get("html_diffs"))

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
