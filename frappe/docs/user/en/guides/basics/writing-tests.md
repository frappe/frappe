# Writing Tests

### Introduction

Frappe provides some basic tooling to quickly write automated tests. There are some basic rules:

1. Test can be anywhere in your repository but must begin with `test_` and should be a `.py` file.
1. Tests must run on a site that starts with `test_`. This is to prevent accidental loss of data.
1. Test stubs are automatically generated for new DocTypes.
1. Frappe test runner will automatically build test records for dependant DocTypes identified by the `Link` type field (Foreign Key)
1. Tests can be executed using `bench run-tests`
1. For non-DocType tests, you can write simple unittests and prefix your file names with `test_`.

### Tests for a DocType

#### Writing DocType Tests:

1. Records that are used for testing are stored in a file `test_records.json` in the doctype folder. [For example see the Event Tests](https://github.com/frappe/frappe/blob/develop/frappe/core/doctype/event/test_records.json).
1. Test cases are in a file named `test_[doctype].py`
1. To provide the test records (and dependencies) call `test_records = frappe.get_test_records('Event')` in your test case file.

#### Example (for `test_records.json`):

	[
		{
			"doctype": "Event",
			"subject":"_Test Event 1",
			"starts_on": "2014-01-01",
			"event_type": "Public"
		},
		{
			"doctype": "Event",
			"starts_on": "2014-01-01",
			"subject":"_Test Event 2",
			"event_type": "Private"
		},
		{
			"doctype": "Event",
			"starts_on": "2014-01-01",
			"subject":"_Test Event 3",
			"event_type": "Private",
			"event_individuals": [{
				"person": "test1@example.com"
			}]
		}
	]


#### Example (for `test_event.py`):

	# Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
	# MIT License. See license.txt

	import frappe
	import frappe.defaults
	import unittest

	# load test records and dependencies
	test_records = frappe.get_test_records('Event')

	class TestEvent(unittest.TestCase):
		def tearDown(self):
			frappe.set_user("Administrator")

		def test_allowed_public(self):
			frappe.set_user("test1@example.com")
			doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject":"_Test Event 1"}))
			self.assertTrue(frappe.has_permission("Event", doc=doc))

		def test_not_allowed_private(self):
			frappe.set_user("test1@example.com")
			doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject":"_Test Event 2"}))
			self.assertFalse(frappe.has_permission("Event", doc=doc))

		def test_allowed_private_if_in_event_user(self):
			frappe.set_user("test1@example.com")
			doc = frappe.get_doc("Event", frappe.db.get_value("Event", {"subject":"_Test Event 3"}))
			self.assertTrue(frappe.has_permission("Event", doc=doc))

		def test_event_list(self):
			frappe.set_user("test1@example.com")
			res = frappe.get_list("Event", filters=[["Event", "subject", "like", "_Test Event%"]], fields=["name", "subject"])
			self.assertEquals(len(res), 2)
			subjects = [r.subject for r in res]
			self.assertTrue("_Test Event 1" in subjects)
			self.assertTrue("_Test Event 3" in subjects)
			self.assertFalse("_Test Event 2" in subjects)

#### Running Tests

To run a test for a doctype

	bench run-tests --doctype [doctype]

This function will build all the test dependencies and run your tests.

### Running All Tests

To run all tests:

	bench run-tests

---

## Client Side Testing (Using Selenium)

> This feature is still under development.

For an example see, [https://github.com/frappe/erpnext/blob/develop/erpnext/tests/sel_tests.py](https://github.com/frappe/erpnext/blob/develop/erpnext/tests/sel_tests.py)
