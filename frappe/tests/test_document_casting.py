import types
import unittest
from unittest.mock import MagicMock, call, patch

import frappe
from frappe.model.document import Document
from frappe.permissions import FUNC_CLOSURE_PERMISSION_REQUIREMENTS, requires_permission


def create_test_doctypes():
	if not frappe.db.exists("DocType", "TestDocType"):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "TestDocType",
				"module": "Custom",
				"custom": 1,
				"fields": [{"fieldname": "test_field", "fieldtype": "Data"}],
			}
		).insert()

	if not frappe.db.exists("DocType", "SourceDocType"):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "SourceDocType",
				"module": "Custom",
				"custom": 1,
				"fields": [{"fieldname": "source_field", "fieldtype": "Data"}],
			}
		).insert()

	if not frappe.db.exists("DocType", "TargetDocType"):
		frappe.get_doc(
			{
				"doctype": "DocType",
				"name": "TargetDocType",
				"module": "Custom",
				"custom": 1,
				"fields": [{"fieldname": "target_field", "fieldtype": "Data"}],
			}
		).insert()


class WithTestDocuments(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		create_test_doctypes()

	def setUp(self):
		self.source_doc = frappe.new_doc(
			"SourceDocType",
			**{
				"name": "SOURCE-001",
				"source_field": "source value",
			},
		).insert()
		self.test_doc = frappe.new_doc(
			"TestDocType",
			**{
				"name": "TEST-001",
				"test_field": "test value",
			},
		).insert()
		self.target_doc = frappe.new_doc(
			"TargetDocType",
			**{
				"name": "TARGET-001",
				"target_field": "target value",
			},
		).insert()
		frappe.db.commit()
		# Mock the conversion methods
		self.source_doc._into_testdoctype = MagicMock()
		self.test_doc._from_sourcedoctype = MagicMock()
		self.test_doc._into_targetdoctype = MagicMock()
		self.target_doc._from_testdoctype = MagicMock()

	def tearDown(self):
		frappe.set_user("Administrator")
		for doctype in ["TestDocType", "SourceDocType", "TargetDocType"]:
			frappe.db.delete(doctype)
			frappe.db.commit()
		# Custom Doctypes have no dedicated classes
		if hasattr(Document, "_into_testdoctype"):
			del Document._into_testdoctype
		if hasattr(Document, "_from_sourcedoctype"):
			del Document._from_sourcedoctype
		if hasattr(Document, "_into_targetdoctype"):
			del Document._into_targetdoctype
		if hasattr(Document, "_from_testdoctype"):
			del Document._from_testdoctype


class TestDocumentCaster(WithTestDocuments):
	# Tests for from_doc method
	@patch("frappe.get_doc")
	def test_from_doc_with_from_method(self, mock_get_doc):
		mock_get_doc.return_value = self.source_doc
		self.test_doc.from_doc("SourceDocType", "SOURCE-001")
		self.test_doc._from_sourcedoctype.assert_called_once_with(
			self.source_doc, whitelist_permissions=False
		)

	@patch("frappe.get_doc")
	def test_from_doc_with_into_method(self, mock_get_doc):
		mock_get_doc.return_value = self.source_doc
		# Remove existing preferenctial conversion method
		del self.test_doc._from_sourcedoctype
		self.test_doc.from_doc("SourceDocType", "SOURCE-001")
		self.source_doc._into_testdoctype.assert_called_once_with(self.test_doc, whitelist_permissions=False)

	@patch("frappe.get_doc")
	def test_from_doc_no_conversion_method(self, mock_get_doc):
		mock_get_doc.return_value = self.source_doc
		# Remove any existing conversion methods
		del self.test_doc._from_sourcedoctype
		del self.source_doc._into_testdoctype

		with self.assertRaises(NotImplementedError) as context:
			self.test_doc.from_doc("SourceDocType", "SOURCE-001")

		self.assertIn("No conversion method found", str(context.exception))
		self.assertIn("TestDocType does not implement '_from_sourcedoctype'", str(context.exception))
		self.assertIn("SourceDocType does not implement '_into_testdoctype'", str(context.exception))

	@patch("frappe.get_doc")
	def test_from_doc_whitelist_permissions(self, mock_get_doc):
		mock_get_doc.return_value = self.source_doc
		self.test_doc.from_doc("SourceDocType", "SOURCE-001", whitelist_permissions=True)
		self.test_doc._from_sourcedoctype.assert_called_once_with(self.source_doc, whitelist_permissions=True)

	# Tests for into method
	@patch("frappe.get_doc")
	def test_into_with_into_method(self, mock_get_doc):
		mock_get_doc.return_value = self.target_doc
		result = self.test_doc.into("TargetDocType")
		self.assertIsInstance(result, Document)
		self.assertEqual(result.doctype, "TargetDocType")
		self.test_doc._into_targetdoctype.assert_called_once_with(
			self.target_doc, whitelist_permissions=False
		)

	@patch("frappe.get_doc")
	def test_into_with_from_method(self, mock_get_doc):
		mock_get_doc.return_value = self.target_doc
		# Remove existing preferenctial conversion method
		del self.test_doc._into_targetdoctype
		result = self.test_doc.into("TargetDocType")
		self.assertIsInstance(result, Document)
		self.assertEqual(result.doctype, "TargetDocType")
		self.target_doc._from_testdoctype.assert_called_once_with(self.test_doc, whitelist_permissions=False)

	def test_into_no_conversion_method(self):
		# Remove any existing conversion methods
		if hasattr(self.target_doc, "_from_testdoctype"):
			del self.target_doc._from_testdoctype
		if hasattr(self.test_doc, "_into_targetdoctype"):
			del self.test_doc._into_targetdoctype

		with self.assertRaises(NotImplementedError) as context:
			self.test_doc.into("TargetDocType")

		self.assertIn("No conversion method found", str(context.exception))
		self.assertIn("TestDocType does not implement '_into_targetdoctype'", str(context.exception))
		self.assertIn("TargetDocType does not implement '_from_testdoctype'", str(context.exception))

	@patch("frappe.get_doc")
	def test_into_whitelist_permissions(self, mock_get_doc):
		mock_get_doc.return_value = self.target_doc
		result = self.test_doc.into("TargetDocType", whitelist_permissions=True)
		self.assertIsInstance(result, Document)
		self.assertEqual(result.doctype, "TargetDocType")
		self.test_doc._into_targetdoctype.assert_called_once_with(result, whitelist_permissions=True)


class TestDocCastingFlow(WithTestDocuments):
	def test_new_doc_from(self):
		def _from_sourcedoctype(self, source_doc, whitelist_permissions=False):
			# This side effect will set a custom attribute on the target document
			self.test_field = source_doc.source_field

		Document._from_sourcedoctype = _from_sourcedoctype
		# doctype + docname calling convention
		result = frappe.new_doc_from("TestDocType", "SourceDocType", self.source_doc.name)
		self.assertEqual(result.doctype, "TestDocType")
		self.assertEqual(result.test_field, self.source_doc.source_field)

		# doc instance calling convention
		result = frappe.new_doc_from("TestDocType", self.source_doc)
		self.assertEqual(result.doctype, "TestDocType")
		self.assertEqual(result.test_field, self.source_doc.source_field)

	def test_doc_from_doc(self):
		def _from_sourcedoctype(self, source_doc, whitelist_permissions=False):
			# This side effect will set a custom attribute on the target document
			self.test_field = source_doc.source_field

		self.test_doc._from_sourcedoctype = types.MethodType(_from_sourcedoctype, self.test_doc)
		# doctype + docname calling convention
		result = self.test_doc.from_doc("SourceDocType", self.source_doc.name)
		self.assertEqual(result.doctype, "TestDocType")
		self.assertEqual(result.test_field, self.source_doc.source_field)

		# doc instance calling convention
		result = self.test_doc.from_doc(self.source_doc)
		self.assertEqual(result.doctype, "TestDocType")
		self.assertEqual(result.test_field, self.source_doc.source_field)

	def test_doc_into(self):
		def _into_targetdoctype(self, target_doc, whitelist_permissions=False):
			# This side effect will set a custom attribute on the target document
			target_doc.target_field = self.test_field

		self.test_doc._into_targetdoctype = types.MethodType(_into_targetdoctype, self.test_doc)
		result = self.test_doc.into("TargetDocType")
		self.assertEqual(result.doctype, "TargetDocType")
		self.assertEqual(result.target_field, self.test_doc.test_field)


class TestRequiresPermission(unittest.TestCase):
	@classmethod
	def setUpClass(cls):
		create_test_doctypes()

	def setUp(self):
		frappe.set_user("Administrator")
		FUNC_CLOSURE_PERMISSION_REQUIREMENTS.clear()

	def tearDown(self):
		frappe.set_user("Administrator")
		FUNC_CLOSURE_PERMISSION_REQUIREMENTS.clear()

	def test_single_permission_requirement(self):
		@requires_permission("TestDocType", "read")
		def test_func():
			return "Success"

		self.assertEqual(test_func(), "Success")

	def test_multiple_permission_requirements(self):
		@requires_permission("TestDocType", "read")
		@requires_permission("TestDocType", "write")
		def test_func():
			return "Success"

		self.assertEqual(test_func(), "Success")

	def test_list_permission_requirements(self):
		@requires_permission([("TestDocType", "read"), ("TestDocType", "write")])
		def test_func():
			return "Success"

		self.assertEqual(test_func(), "Success")

	def test_permission_denied(self):
		@requires_permission("TestDocType", "delete")
		def test_func():
			return "Success"

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError):
			test_func()

	def test_whitelist_permissions(self):
		@requires_permission("TestDocType", "delete")
		def test_func():
			return "Success"

		frappe.set_user("Guest")
		self.assertEqual(test_func(whitelist_permissions=True), "Success")

	def test_multiple_doctypes_permissions(self):
		@requires_permission("TestDocType", "read")
		@requires_permission("SourceDocType", "write")
		def test_func():
			return "Success"

		self.assertEqual(test_func(), "Success")

	def test_permission_error_message(self):
		@requires_permission("TestDocType", "delete")
		@requires_permission("SourceDocType", "write")
		def test_func():
			return "Success"

		frappe.set_user("Guest")
		with self.assertRaises(frappe.PermissionError) as context:
			test_func()

		self.assertIn("No delete permission for TestDocType", str(context.exception))
		self.assertIn("No write permission for SourceDocType", str(context.exception))
