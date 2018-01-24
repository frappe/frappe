# Unit Testing

## 1.Introduction

Frappé provides some basic tooling to quickly write automated tests. There are some basic rules:

1. Test can be anywhere in your repository but must begin with `test_` and should be a `.py` file.
1. Tests must run on a site that starts with `test_`. This is to prevent accidental loss of data.
1. Test stubs are automatically generated for new DocTypes.
1. Frappé test runner will automatically build test records for dependant DocTypes identified by the `Link` type field (Foreign Key)
1. Tests can be executed using `bench run-tests`
1. For non-DocType tests, you can write simple unittests and prefix your file names with `test_`.

## 2. Running Tests

This function will build all the test dependencies and run your tests.
You should run tests from "frappe_bench" folder. Without options all tests will be run.

	bench run-tests

If you need more information about test execution - you can use verbose log level for bench.

	bench --verbose run-tests

### Options:

	--app <AppName>
	--doctype <DocType>
	--test <SpecificTest>
	--module <Module> (Run a particular module that has tests)
	--profile (Runs a Python profiler on the test)
	--junit-xml-output<PathToXML> (The command provides test results in the standard XUnit XML format)

#### 2.1. Example for app:
All applications are located in folder: "~/frappe-bench/apps".
We can run tests for each application.

	- frappe-bench/apps/erpnext/
	- frappe-bench/apps/erpnext_demo/
	- frappe-bench/apps/frappe/

	bench run-tests --app erpnext
	bench run-tests --app erpnext_demo
	bench run-tests --app frappe


#### 2.2. Example for doctype:

	frappe@erpnext:~/frappe-bench$ bench run-tests --doctype "Activity Cost"
	.
	----------------------------------------------------------------------
	Ran 1 test in 0.008s

	OK

#### 2.3. Example for test:
Run a specific case in User:

	frappe@erpnext:~/frappe-bench$ bench run-tests --doctype User --test test_get_value
	.
	----------------------------------------------------------------------
	Ran 1 test in 0.005s

	OK

#### 2.4. Example for module:
If we want to run tests in the module:

	/home/frappe/frappe-bench/apps/erpnext/erpnext/support/doctype/issue/test_issue.py

We should use module name like this (related to application folder)

	erpnext.support.doctype.issue.test_issue

#####EXAMPLE:

	frappe@erpnext:~/frappe-bench$ bench run-tests --module "erpnext.stock.doctype.stock_entry.test_stock_entry"
	...........................
	----------------------------------------------------------------------
	Ran 27 tests in 30.549s


#### 2.5. Example for profile:

	frappe@erpnext:~/frappe-bench$ bench run-tests --doctype "Activity Cost" --profile
	.
	----------------------------------------------------------------------
	Ran 1 test in 0.010s

	OK
	         9133 function calls (8912 primitive calls) in 0.011 seconds

	   Ordered by: cumulative time

	   ncalls  tottime  percall  cumtime  percall filename:lineno(function)
	        2    0.000    0.000    0.008    0.004 /home/frappe/frappe-bench/apps/frappe/frappe/model/document.py:187(insert)
	        1    0.000    0.000    0.003    0.003 /home/frappe/frappe-bench/apps/frappe/frappe/model/document.py:386(_validate)
	       13    0.000    0.000    0.002    0.000 /home/frappe/frappe-bench/apps/frappe/frappe/database.py:77(sql)
	      255    0.000    0.000    0.002    0.000 /home/frappe/frappe-bench/apps/frappe/frappe/model/base_document.py:91(get)
	       12    0.000    0.000    0.002    0.000

#### 2.6. Example for XUnit XML:

##### How to run:

	bench run-tests --junit-xml-output=/reports/junit_test.xml

##### Example of test report:

	<testsuite tests="3">
	    <testcase classname="foo1" name="ASuccessfulTest"/>
	    <testcase classname="foo2" name="AnotherSuccessfulTest"/>
	    <testcase classname="foo3" name="AFailingTest">
	        <failure type="NotEnoughFoo"> details about failure </failure>
	    </testcase>
	</testsuite>

It’s designed for the CI Jenkins, but will work for anything else that understands an XUnit-formatted XML representation of test results.

#### Jenkins configuration support:
1. You should install xUnit plugin - https://wiki.jenkins-ci.org/display/JENKINS/xUnit+Plugin
2. After installation open Jenkins job configuration, click the box named “Publish JUnit test result report” under the "Post-build Actions" and enter path to XML report:
(Example: _reports/*.xml_)

## 3. Tests for a DocType

### 3.1. Writing DocType Tests:

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

	# Copyright (c) 2015, Frappé Technologies Pvt. Ltd. and Contributors
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

