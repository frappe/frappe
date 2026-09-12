from frappe.model.base_document import BaseDocument
from frappe.tests.utils import FrappeTestCase


<<<<<<< HEAD
class TestBaseDocument(FrappeTestCase):
=======
class TestExtensionA(BaseDocument):
	def extension_method_a(self):
		return "method_a"


class TestExtensionB(BaseDocument):
	def extension_method_b(self):
		return "method_b"


class TestToDoExtension(BaseDocument):
	"""Extension class that overrides ToDo's validate method"""

	def validate(self):
		# Add our custom logic
		self.custom_validation_called = True

	def extension_method(self):
		return "extension_method_called"


class TestBaseDocument(IntegrationTestCase):
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

>>>>>>> 524f31727e (test: add regression test for json sanity)
	def test_docstatus(self):
		doc = BaseDocument({"docstatus": 0, "doctype": "ToDo"})
		self.assertTrue(doc.docstatus.is_draft())
		self.assertEqual(doc.docstatus, 0)

		doc.docstatus = 1
		self.assertTrue(doc.docstatus.is_submitted())
		self.assertEqual(doc.docstatus, 1)

		doc.docstatus = 2
		self.assertTrue(doc.docstatus.is_cancelled())
		self.assertEqual(doc.docstatus, 2)
