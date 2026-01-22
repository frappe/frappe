import pickle

import frappe
from frappe.desk.doctype.todo.todo import ToDo
from frappe.model.base_document import BaseDocument, _get_extended_class
from frappe.tests import IntegrationTestCase


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
			"frappe.tests.test_base_document.TestExtensionA",
			"frappe.tests.test_base_document.TestExtensionB",
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
		extensions = ["frappe.tests.test_base_document.TestToDoExtension"]

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
			"frappe.tests.test_base_document.TestExtensionA",  # valid
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
		extensions = ["frappe.tests.test_base_document.TestToDoExtension"]

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
			# These should be excluded by BaseDocument's __getstate__
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


def clear_todo_controller_cache():
	"""Helper method to clear controller cache for ToDo"""
	if hasattr(frappe, "controllers") and frappe.local.site in frappe.controllers:
		frappe.controllers[frappe.local.site].pop("ToDo", None)
