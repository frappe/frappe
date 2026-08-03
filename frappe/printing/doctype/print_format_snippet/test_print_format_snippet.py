# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json
from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase

SECTION = {"label": "Totals", "columns": [{"label": "", "fields": []}]}


class TestPrintFormatSnippet(IntegrationTestCase):
	def make(self, name, **kwargs):
		kwargs.setdefault("snippet_type", "Section")
		kwargs.setdefault("content", json.dumps(SECTION))
		doc = frappe.get_doc({"doctype": "Print Format Snippet", "name": name, **kwargs})
		doc.insert()
		self.addCleanup(frappe.delete_doc, "Print Format Snippet", name, force=True)
		return doc

	def test_content_round_trips(self):
		doc = self.make("_Test Section Snippet", document_type="ToDo")
		self.assertEqual(json.loads(doc.content), SECTION)

	def test_field_snippet_without_document_type_is_global(self):
		doc = self.make(
			"_Test Field Snippet", snippet_type="Field", content=json.dumps({"fieldname": "status"})
		)
		self.assertFalse(doc.document_type)

	def test_content_must_be_a_json_object(self):
		for bad in ("not json", "[1, 2]", '"a string"'):
			with self.subTest(content=bad):
				doc = frappe.get_doc(
					{
						"doctype": "Print Format Snippet",
						"name": "_Test Bad Snippet",
						"snippet_type": "Section",
						"content": bad,
					}
				)
				self.assertRaises(frappe.ValidationError, doc.insert)

	def test_missing_content_reports_mandatory_not_a_crash(self):
		doc = frappe.get_doc(
			{
				"doctype": "Print Format Snippet",
				"name": "_Test Empty Snippet",
				"snippet_type": "Section",
			}
		)
		self.assertRaises(frappe.MandatoryError, doc.insert)

	def test_standard_requires_developer_mode(self):
		doc = frappe.get_doc(
			{
				"doctype": "Print Format Snippet",
				"name": "_Test Standard Snippet",
				"snippet_type": "Section",
				"content": json.dumps(SECTION),
				"standard": 1,
				"module": "Printing",
			}
		)
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			self.assertRaises(frappe.ValidationError, doc.insert)
