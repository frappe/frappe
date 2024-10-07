# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
"""
DEPRECATED.

This entire file is deprecated and will be removed in v17.

DO NOT ADD ANYTHING!
"""

from frappe.commands.testing import main
from frappe.testing.result import SLOW_TEST_THRESHOLD


def xmlrunner_wrapper(output):
	"""Convenience wrapper to keep method signature unchanged for XMLTestRunner and TextTestRunner"""
	try:
		import xmlrunner
	except ImportError:
		print("Development dependencies are required to execute this command. To install run:")
		print("$ bench setup requirements --dev")
		raise

	def _runner(*args, **kwargs):
		kwargs["output"] = output
		return xmlrunner.XMLTestRunner(*args, **kwargs)

	return _runner


from frappe.tests.utils import (
	TestRecordLog,
	get_dependencies,
	get_modules,
	make_test_objects,
	make_test_records,
	make_test_records_for_doctype,
	print_mandatory_fields,
)


# Compatibility functions
def add_to_test_record_log(doctype):
	TestRecordLog().add(doctype)


def get_test_record_log():
	return TestRecordLog().get()
