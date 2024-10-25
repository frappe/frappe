import sys
import unittest
from collections.abc import Iterable
from unittest.mock import Mock, call, patch

import frappe
from frappe import _dict, scrub
from frappe.custom.doctype.custom_field.custom_field import create_custom_field
from frappe.model.document import Document, DocumentProxy
from frappe.tests import IntegrationTestCase, UnitTestCase
from frappe.utils.jinja import process_context, render_template


class TestDocumentProxy(UnitTestCase):
	def setUp(self):
		self.mock_doc = Mock(spec=Document, doctype="Test DocType")
		self.mock_doc.name = "TEST001"

		self.mock_meta = Mock()
		self.mock_meta.fields = [
			_dict({"fieldname": "test_field", "fieldtype": "Data"}),
			_dict({"fieldname": "child_field", "fieldtype": "Data"}),
			_dict({"fieldname": "link_field", "fieldtype": "Link", "options": "Linked DocType"}),
			_dict(
				{
					"fieldname": "dynamic_link_field",
					"fieldtype": "Dynamic Link",
					"options": "link_doctype_field",
				}
			),
			_dict({"fieldname": "link_doctype_field", "fieldtype": "Link", "options": "DocType"}),
			_dict({"fieldname": "table_field", "fieldtype": "Table", "options": "Child DocType"}),
			_dict(
				{
					"fieldname": "table_multiselect_field",
					"fieldtype": "Table MultiSelect",
					"options": "Child DocType",
				}
			),
		]

		# Mock child table data
		child_mock_1 = Mock(spec=Document, doctype="Child DocType")
		child_mock_1.name = "CHILD001"
		child_mock_2 = Mock(spec=Document, doctype="Child DocType")
		child_mock_2.name = "CHILD002"
		self.mock_child_docs = [child_mock_1, child_mock_2]

		self.mock_doc.get.side_effect = lambda field: {
			"test_field": "Test Value",
			"link_field": "LINK001",
			"child_field": "Child Value",
			"dynamic_link_field": "DYNAMIC001",
			"link_doctype_field": "Some DocType",
			"table_field": self.mock_child_docs,
			"table_multiselect_field": self.mock_child_docs,
		}.get(field)

		self.mock_get_meta = patch("frappe.get_meta", return_value=self.mock_meta).start()
		self.mock_get_doc = patch("frappe.get_doc", return_value=self.mock_doc).start()

		# Add this assertion to ensure the mock_doc is recognized as a Document instance
		self.assertTrue(isinstance(self.mock_doc, Document))

	def tearDown(self):
		patch.stopall()
		DocumentProxy._get_fields.cache_clear()  # Clear the LRU cache

	def test_document_proxy_creation(self):
		proxy = DocumentProxy("Test DocType", "TEST001")

		self.assertEqual(proxy.doctype, "Test DocType")
		self.assertEqual(proxy.name, "TEST001")
		self.assertEqual(str(proxy), "TEST001")

	def test_document_proxy_field_access(self):
		proxy = DocumentProxy("Test DocType", "TEST001")

		# Assert that get_doc is not called before field access
		self.mock_get_doc.assert_not_called()

		# Access a field
		self.assertEqual(proxy.test_field, "Test Value")

		# Now assert that get_doc has been called once
		self.mock_get_doc.assert_called_once_with("Test DocType", "TEST001")

	def test_document_proxy_field_caching(self):
		# Create two different DocumentProxy instances for the same doctype
		proxy1 = DocumentProxy("Test DocType", "TEST001")
		proxy2 = DocumentProxy("Test DocType", "TEST002")

		# Access a field on the first proxy to trigger _get_fields
		_ = proxy1.test_field

		# Reset the mock to clear the call count
		self.mock_get_meta.reset_mock()

		# Access a field on the second proxy
		_ = proxy2.test_field

		# Assert that get_meta was not called again
		self.mock_get_meta.assert_not_called()

		# Create a DocumentProxy for a different doctype
		proxy3 = DocumentProxy("Another DocType", "TEST003")

		# Access a field on the new proxy
		_ = proxy3.test_field

		# Assert that get_meta was called once for the new doctype
		self.mock_get_meta.assert_called_once_with("Another DocType")

	def test_document_proxy_link_field(self):
		proxy = DocumentProxy("Test DocType", "TEST001")
		linked_proxy = proxy.link_field

		self.assertIsInstance(linked_proxy, DocumentProxy)
		self.assertEqual(linked_proxy.doctype, "Linked DocType")
		self.assertEqual(linked_proxy.name, "LINK001")

	def test_document_proxy_invalid_field(self):
		proxy = DocumentProxy("Test DocType", "TEST001")

		with self.assertRaises(AttributeError):
			proxy.invalid_field

	def test_document_proxy_contains(self):
		proxy = DocumentProxy("Test DocType", "TEST001")

		# Test for existing fields
		self.assertIn("test_field", proxy)
		self.assertIn("link_field", proxy)

		# Test for non-existing field
		self.assertNotIn("non_existing_field", proxy)

		# Ensure that __contains__ doesn't trigger document fetch
		self.mock_get_doc.assert_not_called()

		# Access a field to trigger document fetch
		_ = proxy.test_field

		# Check that get_doc was called once
		self.mock_get_doc.assert_called_once_with("Test DocType", "TEST001")

		# Test again after document fetch
		self.assertIn("test_field", proxy)
		self.assertNotIn("non_existing_field", proxy)

	def test_document_proxy_dynamic_link_field(self):
		proxy = DocumentProxy("Test DocType", "TEST001")
		dynamic_link_value = proxy.dynamic_link_field

		self.assertIsInstance(dynamic_link_value, DocumentProxy)
		self.assertEqual(dynamic_link_value.name, "DYNAMIC001")
		self.assertEqual(dynamic_link_value.doctype, "Some DocType")

	def test_document_proxy_table_field(self):
		proxy = DocumentProxy("Test DocType", "TEST001")
		table_field = proxy.table_field

		self.assertIsInstance(table_field, Iterable)
		self.assertEqual(len(table_field), 2)
		self.assertIsInstance(table_field[0], DocumentProxy)
		self.assertEqual(table_field[0].child_field, "Child Value")
		self.assertEqual(table_field[0].name, "CHILD001")

	def test_document_proxy_table_multiselect_field(self):
		proxy = DocumentProxy("Test DocType", "TEST001")
		table_multiselect_field = proxy.table_multiselect_field

		self.assertIsInstance(table_multiselect_field, Iterable)
		self.assertEqual(len(table_multiselect_field), 2)
		self.assertIsInstance(table_multiselect_field[0], DocumentProxy)
		self.assertEqual(table_multiselect_field[1].child_field, "Child Value")
		self.assertEqual(table_multiselect_field[1].name, "CHILD002")


class TestProcessContext(UnitTestCase):
	def setUp(self):
		self.mock_doc = Mock(spec=Document, doctype="Test DocType")
		self.mock_doc.name = "TEST001"
		self.mock_doc.get.side_effect = lambda field: {
			"owner": "test@example.com",
			"creation": "2024-10-03 12:00:00",
			"modified": "2024-10-03 12:00:00",
			"modified_by": "test@example.com",
			"docstatus": 0,
			"idx": 1,
			"test_field": "Test Value",
			"link_field": "LINK001",
		}[field]

		self.mock_meta = Mock()
		self.mock_meta.fields = [
			_dict({"fieldname": "test_field", "fieldtype": "Data"}),
			_dict(
				{"fieldname": "link_field", "fieldtype": "Link", "options": "Linked DocType"}
			),  # nests in the mock
		]

		self.mock_get_meta = patch("frappe.get_meta", return_value=self.mock_meta).start()
		self.mock_get_doc = patch("frappe.get_doc", return_value=self.mock_doc).start()

		# Add this assertion to ensure the mock_doc is recognized as a Document instance
		self.assertTrue(isinstance(self.mock_doc, Document))

	def tearDown(self):
		patch.stopall()
		DocumentProxy._get_fields.cache_clear()  # Clear the LRU cache

	def test_process_context_non_completion(self):
		context = {
			"doc": self.mock_doc,  # Level 0
			"value": "test",
			"list": [1, 2, 3],
			"dict": {
				"key": "value",
				"nested_doc": self.mock_doc,  # Infinite recursion
				"deeper": {
					"nested_doc": self.mock_doc,  # Level 2
					"deepest": {
						"nested_doc": self.mock_doc,  # Level 3
					},
				},
			},
		}

		processed = process_context(context)

		# Check level 0
		self.assertIsInstance(processed["doc"], DocumentProxy)

		# Check Recursion
		self.assertIsInstance(processed["dict"]["nested_doc"], DocumentProxy)
		self.assertIsInstance(processed["dict"]["nested_doc"].link_field, DocumentProxy)
		self.assertIsInstance(processed["dict"]["nested_doc"]["link_field"]["link_field"], DocumentProxy)

		# Check level 2
		self.assertIsInstance(processed["dict"]["deeper"]["nested_doc"], DocumentProxy)

		# Check level 3 (should not be a DocumentProxy)
		self.assertNotIsInstance(processed["dict"]["deeper"]["deepest"]["nested_doc"], DocumentProxy)

		# Check other values remain unchanged
		self.assertEqual(processed["value"], "test")
		self.assertEqual(processed["list"], [1, 2, 3])
		self.assertEqual(processed["dict"]["key"], "value")

	def test_process_context_completion(self):
		context = {"doc": self.mock_doc, "value": "test", "list": [1, 2, 3], "dict": {"key": "value"}}

		# Reset the call count before running the function
		self.mock_get_meta.reset_mock()
		completion_list = process_context(context, for_code_completion=True)
		# Assert that get_meta was called exactly three times with the correct doctypes
		self.assertEqual(self.mock_get_meta.call_count, 3)
		self.mock_get_meta.assert_has_calls(
			[call("Test DocType"), call("Linked DocType"), call("User")], any_order=True
		)
		expected_items = [
			{"value": "doc.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.name", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.name", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.name", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.name", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.idx", "score": 6, "meta": "ctx"},
			{"value": "doc", "score": 6, "meta": "ctx"},
			{"value": "value", "score": 6, "meta": "ctx"},
			{"value": "list", "score": 6, "meta": "ctx"},
			{"value": "dict.key", "score": 6, "meta": "ctx"},
		]

		self.assertEqual(completion_list, expected_items)

	def test_process_context_completion_with_get_keys_for_autocomplete(self):
		from frappe.utils.safe_exec import NamespaceDict

		# Mock frappe namespace
		mock_frappe = NamespaceDict(
			**{
				"get_doc": lambda doctype, name: None,
				"db": {
					"get_value": lambda doctype, filters, fieldname: None,
					"set_value": lambda doctype, name, field, value: None,
				},
				"utils": {
					"now": lambda: None,
					"cstr": lambda text: str(text),
					"cint": lambda text: int(text),
				},
			}
		)

		context = {
			"doc": self.mock_doc,
			"function": lambda x: x * 2,
			"frappe": mock_frappe,  # Add mock frappe namespace
		}

		completion_list = process_context(context, for_code_completion=True)
		expected_items = [
			{"value": "doc.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.name", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.name", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.name", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.owner.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.test_field", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.link_field", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.doctype", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.name", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.owner", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.creation", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.modified", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by.idx", "score": 6, "meta": "ctx"},
			{"value": "doc.modified_by", "score": 6, "meta": "ctx"},
			{"value": "doc.docstatus", "score": 6, "meta": "ctx"},
			{"value": "doc.idx", "score": 6, "meta": "ctx"},
			{"value": "doc", "score": 6, "meta": "ctx"},
			{"value": "function", "score": 9, "meta": "ctx"},
			{"value": "frappe.get_doc", "score": 9, "meta": "ctx"},
			{"value": "frappe.db.get_value", "score": 9, "meta": "ctx"},
			{"value": "frappe.db.set_value", "score": 9, "meta": "ctx"},
			{"value": "frappe.utils.now", "score": 9, "meta": "ctx"},
			{"value": "frappe.utils.cstr", "score": 9, "meta": "ctx"},
			{"value": "frappe.utils.cint", "score": 9, "meta": "ctx"},
		]

		self.assertEqual(completion_list, expected_items)


class CustomDocumentProxy(DocumentProxy):
	def __getattr__(self, attr):
		if attr in self._fieldnames:
			if self._doc is None:
				self._doc = frappe.get_doc(self.doctype, self.name)
			value = self._doc.get(attr)
			return f"Custom_{value}"
		return super().__getattr__(attr)


class TestCustomDocumentProxy(UnitTestCase):
	def setUp(self):
		self.mock_doc = Mock(spec=Document, doctype="Test DocType")
		self.mock_doc.name = "TEST001"
		self.mock_doc.get.return_value = "Test Value"

		self.mock_meta = Mock()
		self.mock_meta.fields = [
			_dict({"fieldname": "test_field", "fieldtype": "Data"}),
		]

		self.mock_get_meta = patch("frappe.get_meta", return_value=self.mock_meta).start()
		self.mock_get_doc = patch("frappe.get_doc", return_value=self.mock_doc).start()
		# Add this assertion to ensure the mock_doc is recognized as a Document instance
		self.assertTrue(isinstance(self.mock_doc, Document))

	def tearDown(self):
		patch.stopall()
		DocumentProxy._get_fields.cache_clear()  # Clear the LRU cache

	def test_custom_document_proxy(self):
		context = {"doc": self.mock_doc}
		template = "{{ doc.test_field }}"

		with patch("frappe.utils.jinja.get_jenv") as mock_get_jenv:
			mock_jenv = Mock()
			mock_get_jenv.return_value = mock_jenv
			mock_template = Mock()
			mock_jenv.from_string.return_value = mock_template

			# Render with default DocumentProxy
			render_template(template, context)
			args, _ = mock_template.render.call_args
			self.assertIsInstance(args[0]["doc"], DocumentProxy)

			# Render with CustomDocumentProxy
			render_template(template, context, document_proxy_class=CustomDocumentProxy)
			args, _ = mock_template.render.call_args
			self.assertIsInstance(args[0]["doc"], CustomDocumentProxy)
			self.assertEqual(args[0]["doc"].test_field, "Custom_Test Value")

	def test_process_context_with_custom_proxy(self):
		context = {"doc": self.mock_doc}

		# Process context with default DocumentProxy
		processed_default = process_context(context)
		self.assertIsInstance(processed_default["doc"], DocumentProxy)
		self.assertEqual(processed_default["doc"].test_field, "Test Value")

		# Process context with CustomDocumentProxy
		processed_custom = process_context(context, document_proxy_class=CustomDocumentProxy)
		self.assertIsInstance(processed_custom["doc"], CustomDocumentProxy)
		self.assertEqual(processed_custom["doc"].test_field, "Custom_Test Value")


def run_specific_test(test_class, test_case=None):
	if test_case:
		suite = unittest.TestSuite()
		suite.addTest(test_class(test_case))
	else:
		suite = unittest.TestLoader().loadTestsFromTestCase(test_class)

	runner = unittest.TextTestRunner(verbosity=2)
	runner.run(suite)


class TestRenderTemplateIntegration(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Create child doctypes first
		cls.create_child_doctype(
			"User Skill",
			[
				{"fieldname": "skill", "fieldtype": "Data", "label": "Skill"},
				{
					"fieldname": "proficiency",
					"fieldtype": "Select",
					"label": "Proficiency",
					"options": "Beginner\nIntermediate\nExpert",
				},
			],
		)
		cls.create_child_doctype(
			"Favorite Document",
			[
				{
					"fieldname": "document_type",
					"fieldtype": "Link",
					"label": "Document Type",
					"options": "DocType",
				},
				{
					"fieldname": "document_name",
					"fieldtype": "Dynamic Link",
					"label": "Document Name",
					"options": "document_type",
				},
			],
		)

		# Now create custom fields
		create_custom_field(
			"User",
			{
				"fieldname": "reports_to",
				"label": "Reports To",
				"fieldtype": "Link",
				"options": "User",
				"insert_after": "last_name",
			},
		)

		# Create custom fields for Dynamic Link, Table, and Table MultiSelect
		create_custom_field(
			"User",
			{
				"fieldname": "role_type",
				"label": "Role Type",
				"fieldtype": "Link",
				"options": "DocType",
				"insert_after": "reports_to",
			},
		)
		create_custom_field(
			"User",
			{
				"fieldname": "dynamic_role",
				"label": "Dynamic Role",
				"fieldtype": "Dynamic Link",
				"options": "role_type",
				"insert_after": "role_type",
			},
		)
		create_custom_field(
			"User",
			{
				"fieldname": "user_skills",
				"label": "User Skills",
				"fieldtype": "Table",
				"options": "User Skill",
				"insert_after": "dynamic_role",
			},
		)
		create_custom_field(
			"User",
			{
				"fieldname": "favorite_documents",
				"label": "Favorite Documents",
				"fieldtype": "Table MultiSelect",
				"options": "Favorite Document",
				"insert_after": "user_skills",
			},
		)

	@classmethod
	def tearDownClass(cls):
		# Remove custom fields
		frappe.delete_doc("Custom Field", "User-reports_to")
		frappe.delete_doc("Custom Field", "User-role_type")
		frappe.delete_doc("Custom Field", "User-dynamic_role")
		frappe.delete_doc("Custom Field", "User-user_skills")
		frappe.delete_doc("Custom Field", "User-favorite_documents")

		# Remove child doctypes
		frappe.delete_doc("DocType", "User Skill")
		frappe.delete_doc("DocType", "Favorite Document")

	@classmethod
	def create_child_doctype(cls, doctype_name, fields):
		if not frappe.db.exists("DocType", doctype_name):
			doctype = frappe.new_doc("DocType")
			doctype.name = doctype_name
			doctype.module = "Core"
			doctype.istable = 1
			doctype.custom = 1
			for field in fields:
				doctype.append("fields", field)
			doctype.insert(ignore_permissions=True)

	def setUp(self):
		frappe.delete_doc_if_exists("User", "test_render_template@example.com")
		frappe.delete_doc_if_exists("User", "manager_render_template@example.com")
		frappe.delete_doc_if_exists("User", "top_manager_render_template@example.com")

		# Ensure the "Employee" role exists
		if not frappe.db.exists("Role", "Employee"):
			frappe.get_doc({"doctype": "Role", "role_name": "Employee"}).insert(ignore_permissions=True)

		# Set up test data in the database
		self.top_manager = frappe.get_doc(
			{
				"doctype": "User",
				"email": "top_manager_render_template@example.com",
				"first_name": "Top",
				"last_name": "Manager",
			}
		).insert(ignore_permissions=True)

		self.manager = frappe.get_doc(
			{
				"doctype": "User",
				"email": "manager_render_template@example.com",
				"first_name": "Middle",
				"last_name": "Manager",
				"reports_to": self.top_manager.name,  # Link to the top manager
			}
		).insert(ignore_permissions=True)

		self.test_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_render_template@example.com",
				"first_name": "Test",
				"last_name": "User",
				"role_type": "Role",
				"dynamic_role": "Employee",
				"user_skills": [
					{"skill": "Python", "proficiency": "Expert"},
					{"skill": "JavaScript", "proficiency": "Intermediate"},
				],
				"favorite_documents": [
					{"document_type": "User", "document_name": self.manager.name},
					{"document_type": "User", "document_name": self.top_manager.name},
				],
				"reports_to": self.manager.name,  # Link to the middle manager
			}
		).insert(ignore_permissions=True)

	def tearDown(self):
		# Clean up test data
		frappe.delete_doc("User", self.test_user.name, ignore_permissions=True)
		frappe.delete_doc("User", self.manager.name, ignore_permissions=True)
		frappe.delete_doc("User", self.top_manager.name, ignore_permissions=True)

	def test_render_template_from_string(self):
		result = render_template("Hello {{ user }}", {"user": "Test User"})
		self.assertEqual(result, "Hello Test User")

	def test_render_template_with_db_context(self):
		result = render_template("{{ user.first_name }} {{ user.last_name }}", {"user": self.test_user})
		self.assertEqual(result, "Test User")

	def test_render_template_with_filters(self):
		result = render_template('{{ "hello world" | upper }}', {})
		self.assertEqual(result, "HELLO WORLD")

	def test_render_template_from_path(self):
		user = frappe.get_doc("User", self.test_user.name)
		manager = frappe.get_doc("User", self.manager.name)
		director = frappe.get_doc("User", self.top_manager.name)

		result = render_template("frappe/tests/test_template.html", {"user": user})
		self.assertIn(f"Welcome, {user.first_name}", result)
		self.assertIn(f"{user.first_name} reports to {manager.first_name} {manager.last_name}", result)
		self.assertIn(f"who reports to {director.first_name} {director.last_name}", result)

	def test_render_template_with_context_processing(self):
		doc = frappe.get_doc("User", self.test_user.name)
		template = """
		{{ doc.first_name }} {{ doc.last_name }} ({{ doc.email }})
		Reports to: {{ doc.reports_to.first_name }} {{ doc.reports_to.last_name }}
		"""
		result = render_template(template, {"doc": doc})
		expected_output = """
		Test User (test_render_template@example.com)
		Reports to: Middle Manager
		"""
		self.assertEqual(result.strip(), expected_output.strip())

	def test_render_template_with_link_traversal(self):
		template = (
			"{{ user.first_name }} reports to {{ user.reports_to.first_name }} {{ user.reports_to.last_name }}, "
			"who reports to {{ user.reports_to.reports_to.first_name }} {{ user.reports_to.reports_to.last_name }}."
		)
		result = render_template(template, {"user": self.test_user})
		expected_output = "Test reports to Middle Manager, who reports to Top Manager."
		self.assertEqual(result.strip(), expected_output)

	def test_render_template_with_dynamic_link(self):
		template = "{{ user.first_name }}'s role: {{ user.dynamic_role }} ({{ user.role_type }})"
		result = render_template(template, {"user": self.test_user})
		expected_output = "Test's role: Employee (Role)"
		self.assertEqual(result.strip(), expected_output)

	def test_render_template_with_table_field(self):
		template = """
		{{ user.first_name }}'s skills:
		{%- for skill in user.user_skills %}
		- {{ skill.skill }}: {{ skill.proficiency }}
		{%- endfor %}
		"""
		result = render_template(template, {"user": self.test_user})
		expected_output = """
		Test's skills:
		- Python: Expert
		- JavaScript: Intermediate
		"""
		self.assertEqual(result.strip(), expected_output.strip())

	def test_render_template_with_table_multiselect_field(self):
		template = """
		{{ user.first_name }}'s favorite users:
		{%- for fav in user.favorite_documents %}
		- {{ fav.document_name }}
		{%- endfor %}
		"""
		result = render_template(template, {"user": self.test_user})
		expected_output = f"""
		Test's favorite users:
		- {self.manager.name}
		- {self.top_manager.name}
		"""
		self.assertEqual(result.strip(), expected_output.strip())


class TestRenderTemplateWithGlobals(IntegrationTestCase):
	def test_render_template_with_globals(self):
		# Create DocumentProxy instances
		user = DocumentProxy("User", "Administrator")

		context = {"user": user}

		result = render_template("frappe/tests/test_template_globals.html", context)

		self.assertIn("Proxy: <DocumentProxy: doctype=Language name=n/a>", result)

		# Test JSON
		# a n/a document proxy becomes null via the json_handler's evaluation of __value__()
		self.assertIn('JSON Dumps: {\n "lang": null,\n "user": "Administrator"\n}', result)

		# Test frappe.bold
		self.assertIn("<strong>Administrator</strong>", result)

		# Test frappe.get_meta
		self.assertIn("Meta name: User", result)

		# Test frappe.get_doc
		self.assertIn("User dict name: Administrator", result)

		# Test frappe.utils.get_url
		self.assertIn("http://", result)

		# Test frappe.render_template
		self.assertIn("Hello Administrator", result)

		# Test frappe.db.get_value
		self.assertIn("User email: admin@example.com", result)

		# Test scrub
		self.assertIn("administrator", result)


class TestDocumentProxyRendering(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		# Create test users
		cls.test_user = frappe.get_doc(
			{
				"doctype": "User",
				"email": "test_render@example.com",
				"first_name": "Test",
				"last_name": "Render",
				"language": "en",
			}
		).insert(ignore_permissions=True)

		cls.admin_user = frappe.get_doc("User", "Administrator")

	@classmethod
	def tearDownClass(cls):
		# Clean up test data
		frappe.delete_doc("User", cls.test_user.name, ignore_permissions=True)

	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_fallback_behavior(self):
		template = "{{ doc.first_name }} {{ doc.last_name }} {{ doc.middle_name or 'N/A' }}"
		result = render_template(template, {"doc": self.test_user})
		self.assertEqual(result, "Test Render N/A")

	def test_nested_attribute_access(self):
		template = "{{ doc.owner.name }}"
		result = render_template(template, {"doc": self.test_user})
		self.assertEqual(result, "Administrator")

		template = "{{ doc.modified_by.name }}"
		result = render_template(template, {"doc": self.test_user})
		self.assertEqual(result, "Administrator")

	def test_attribute_existence(self):
		template = "{% if 'middle_name' in doc and doc.middle_name %}Has middle name{% elif 'middle_name' in doc %}Has no middle name{% else %}Can't have middle name{% endif %}"
		result = render_template(template, {"doc": self.test_user})
		self.assertEqual(result, "Has no middle name")

	def test_language_specific_field(self):
		template = "{{ doc.language.language_name }}"
		result = render_template(template, {"doc": self.test_user})
		self.assertEqual(result, "English")

	def test_different_user_types(self):
		admin_template = (
			"{{ doc.name }} {% if frappe.get_doc(doc).has_desk_access() %}(Desk Access){% endif %}"
		)
		admin_result = render_template(admin_template, {"doc": self.admin_user})
		self.assertEqual(admin_result, "Administrator (Desk Access)")

		user_result = render_template(admin_template, {"doc": self.test_user})
		self.assertEqual(user_result, "test_render@example.com ")

	def test_document_proxy_in_list(self):
		users = [self.admin_user, self.test_user]
		template = "{% for user in users %}{{ user.name }}{% if not loop.last %}, {% endif %}{% endfor %}"
		result = render_template(template, {"users": users})
		self.assertEqual(result, "Administrator, test_render@example.com")

	def test_document_proxy_in_dict(self):
		user_dict = {"admin": self.admin_user, "test": self.test_user}
		template = "Admin: {{ users.admin.name }}, Test: {{ users.test.name }}"
		result = render_template(template, {"users": user_dict})
		self.assertEqual(result, "Admin: Administrator, Test: test_render@example.com")


if __name__ == "__main__":
	# Mock Frappe environment
	frappe.conf = Mock()
	frappe.conf.developer_mode = False
	frappe.local = Mock()
	frappe.local.site = "test_site"

	def get_test_classes():
		return [
			cls
			for name, cls in globals().items()
			if isinstance(cls, type)
			and issubclass(cls, UnitTestCase)
			and not issubclass(cls, IntegrationTestCase)
		]

	if len(sys.argv) > 1:
		test_class_name = sys.argv[1]
		test_case_name = sys.argv[2] if len(sys.argv) > 2 else None

		# Get the test class by name
		test_class = globals().get(test_class_name)
		if not test_class:
			print(f"Test class '{test_class_name}' not found.")
			sys.exit(1)

		if issubclass(test_class, IntegrationTestCase):
			print(f"Skipping IntegrationTestCase: {test_class_name}")
			sys.exit(0)

		run_specific_test(test_class, test_case_name)
	else:
		# Run all tests except FrappeTestCase instances
		suite = unittest.TestSuite()
		for test_class in get_test_classes():
			suite.addTest(unittest.makeSuite(test_class))

		runner = unittest.TextTestRunner(verbosity=2)
		runner.run(suite)
