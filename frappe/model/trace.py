"""
Traced Fields for Frappe

This module provides utilities for creating traced fields in Frappe documents,
which is particularly useful for instrumenting or debugging test cases and
enforcing strict validation rules.

Key features:
- Create fields that can be monitored for specific value changes
- Enforce forbidden values on fields
- Apply custom validation logic to fields
- Seamlessly integrate with Frappe's document model

Usage in test cases:
1. Subclass your DocType from TracedDocument alongside Document
2. Use traced_field to define fields you want to monitor
3. Specify forbidden values or custom validation functions
4. In your tests, attempt to set values and check for raised exceptions

Example of standard usage:
		from frappe.model.trace import TracedDocument, traced_field

		class CustomSalesInvoice(SalesInvoice, TracedDocument):
			...
			def validate_amount(self, value):
				if value < 0:
					raise AssertionError("Amount cannot be negative")

			loyalty_program = traced_field("Loyalty Program", forbidden_values = ["FORBIDDEN_PROGRAM"])
			amount = traced_field("Amount", custom_validation = validate_amount)
			...

	class TestCustomInvoice(unittest.TestCase):
		def setUp(self):
			self.invoice = CustomSalesInvoice()

		def test_forbidden_loyalty_program(self):
			with self.assertRaises(AssertionError):
				self.invoice.loyalty_program = "FORBIDDEN_PROGRAM"

		def test_negative_amount(self):
			with self.assertRaises(AssertionError):
				self.invoice.amount = -100

Benefits for testing:
- Easily catch unauthorized value changes
- Enforce business rules at the field level
- Improve test coverage by explicitly checking field-level validations
- Simulate and test error conditions more effectively

Monkey Patching for Debugging:
For temporary tracing of fields in existing DocTypes, use the traced_field_context
context manager. This allows you to add tracing to any field without modifying
the original DocType class.

Example of monkey patching with context manager:
	import unittest
	from frappe.model.document import Document
	from frappe.model.trace import traced_field_context

	class TestExistingDocType(unittest.TestCase):
		def test_debug_value(self):
			def validate_some_field(obj, value):
				if value == 'debug_value':
					raise AssertionError("Debug value detected")

			doc = frappe.get_doc("My Doc Type")

			with traced_field_context(
				doc.__class__,
			 'some_field',
				custom_validation=validate_some_field
			):
				with self.assertRaises(AssertionError):
					doc.some_field = 'debug_value'

			# Outside the context, the original behavior is restored
			doc.some_field = 'debug_value'  # This will not raise an error

This approach allows you to:
- Easily add temporary tracing to any field in any DocType
- Debug issues by catching specific value changes
- Add custom validation logic for debugging purposes
- Automatically reverts changes after the context, ensuring no side effects
- Cleaner and more Pythonic approach to temporary monkey patching

Note: While primarily designed for testing, this can also be used in
production code to enforce strict data integrity rules. However, be
mindful of potential performance implications in high-traffic scenarios.
"""

import contextlib

import frappe
from frappe.model.document import Document


class TracedValue:
	"""
	A descriptor class for creating traced fields in Frappe documents.

	This class allows for monitoring and validating changes to specific fields
	in a Frappe document. It can enforce forbidden values and apply custom
	validation logic.

	Attributes:
	        field_name (str): The name of the field being traced.
	        forbidden_values (list): A list of values that are not allowed for this field.
	        custom_validation (callable): A function for custom validation logic.
	"""

	def __init__(self, field_name, forbidden_values=None, custom_validation=None):
		"""
		Initialize a TracedValue instance.

		Args:
		        field_name (str): The name of the field to be traced.
		        forbidden_values (list, optional): A list of values that should not be allowed.
		        custom_validation (callable, optional): A function for additional validation.
		"""
		self.field_name = field_name
		self.forbidden_values = forbidden_values or []
		self.custom_validation = custom_validation

	def __get__(self, obj, objtype=None):
		"""
		Get the value of the traced field.

		Args:
		        obj (object): The instance that this descriptor is accessed from.
		        objtype (type, optional): The type of the instance.

		Returns:
		        The value of the traced field, or self if accessed from the class.
		"""
		if obj is None:
			return self

		return getattr(obj, f"_{self.field_name}", None)

	def __set__(self, obj, value):
		"""
		Set the value of the traced field with validation.

		This method checks against forbidden values and applies custom validation
		before setting the value.

		Args:
		        obj (object): The instance that this descriptor is accessed from.
		        value: The value to set for the traced field.

		Raises:
		        ValueError: If the value is forbidden or fails custom validation.
		            Note: returns AssertionError in test mode to debug with the `--pdb` flag.

		"""
		if value in self.forbidden_values:
			if frappe.flags.in_test:
				frappe.throw(f"{self.field_name} cannot be set to {value}", AssertionError)
			else:
				frappe.throw(f"{self.field_name} cannot be set to {value}")

		if self.custom_validation:
			try:
				self.custom_validation(obj, value)
			except Exception as e:
				if frappe.flags.in_test:
					frappe.throw(str(e), AssertionError)
				else:
					frappe.throw(str(e))

		setattr(obj, f"_{self.field_name}", value)


def traced_field(*args, **kwargs):
	"""
	A convenience function for creating TracedValue instances.

	This function simplifies the creation of traced fields in Frappe documents.

	Args:
	        *args: Positional arguments to pass to TracedValue constructor.
	        **kwargs: Keyword arguments to pass to TracedValue constructor.

	Returns:
	        TracedValue: An instance of the TracedValue descriptor.
	"""
	return TracedValue(*args, **kwargs)


class TracedDocument(Document):
	"""
	A base class for Frappe documents with traced fields.

	This class extends Frappe's Document class to provide support for
	traced fields created with TracedValue.

	Attributes:
	        Inherits all attributes from frappe.model.document.Document
	"""

	def __init__(self, *args, **kwargs):
		"""
		Initialize a TracedDocument instance.

		This method sets up traced fields and initializes the parent Document.

		Args:
		        *args: Positional arguments to pass to the parent constructor.
		        **kwargs: Keyword arguments to pass to the parent constructor.
		"""
		super().__init__(*args, **kwargs)
		for name, attr in self.__class__.__dict__.items():
			if isinstance(attr, TracedValue):
				setattr(self, f"_{name}", getattr(self, name))

	def get_valid_dict(self, *args, **kwargs):
		"""
		Get a valid dictionary representation of the document.

		This method extends the parent method to properly handle traced fields.

		Args:
		        *args: Positional arguments to pass to the parent method.
		        **kwargs: Keyword arguments to pass to the parent method.

		Returns:
		        dict: A dictionary representation of the document, including traced fields.
		"""
		d = super().get_valid_dict(*args, **kwargs)
		for name, attr in self.__class__.__dict__.items():
			if isinstance(attr, TracedValue):
				d[name] = getattr(self, name)
		return d


@contextlib.contextmanager
def traced_field_context(doc_class, field_name, forbidden_values=None, custom_validation=None):
	"""
	A context manager for temporarily tracing a field in a DocType.

	Args:
	        doc_class (type): The DocType class to modify.
	        field_name (str): The name of the field to trace.
	        forbidden_values (list, optional): A list of forbidden values for the field.
	        custom_validation (callable, optional): A custom validation function.

	Yields:
	        None
	"""
	original_attr = getattr(doc_class, field_name, None)
	original_init = doc_class.__init__

	try:
		setattr(doc_class, field_name, traced_field(field_name, forbidden_values, custom_validation))

		def new_init(self, *args, **kwargs):
			original_init(self, *args, **kwargs)
			setattr(self, f"_{field_name}", getattr(self, field_name, None))

		doc_class.__init__ = new_init

		yield

	finally:
		if original_attr is not None:
			setattr(doc_class, field_name, original_attr)
		else:
			delattr(doc_class, field_name)

		doc_class.__init__ = original_init


def trace_fields(**field_configs):
	"""
	A class decorator to permanently trace fields in a DocType.

	Args:
	    **field_configs: Keyword arguments where each key is a field name and
	                     the value is a dict containing 'forbidden_values' and/or
	                     'custom_validation'.

	Returns:
	    callable: A decorator function that modifies the DocType class.
	"""

	def decorator(doc_class):
		original_init = doc_class.__init__

		def new_init(self, *args, **kwargs):
			original_init(self, *args, **kwargs)
			for field_name in field_configs:
				setattr(self, f"_{field_name}", getattr(self, field_name, None))

		doc_class.__init__ = new_init

		for field_name, config in field_configs.items():
			forbidden_values = config.get("forbidden_values")
			custom_validation = config.get("custom_validation")
			setattr(doc_class, field_name, traced_field(field_name, forbidden_values, custom_validation))

		return doc_class

	return decorator
