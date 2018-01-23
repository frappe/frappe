# UI Integration Testing

You can write integration tests using the Selenium Driver. `frappe.utils.selenium_driver` gives you a friendly API to write selenium based tests

To write integration tests, create a standard test case by creating a python file starting with `test_`

All integration tests will be run at the end of the unittests.

### Example

Here is an example of an integration test to check insertion of a To Do

	from __future__ import print_function
	from frappe.utils.selenium_testdriver import TestDriver
	import unittest
	import time

	class TestToDo(unittest.TestCase):
		def setUp(self):
			self.driver = TestDriver()

		def test_todo(self):
			self.driver.login()

			# list view
			self.driver.set_route('List', 'ToDo')

			time.sleep(2)

			# new
			self.driver.click_primary_action()

			time.sleep(2)

			# set input
			self.driver.set_text_editor('description', 'hello')

			# save
			self.driver.click_modal_primary_action()

			time.sleep(2)

			self.assertTrue(self.driver.get_visible_element('.result-list')
				.find_element_by_css_selector('.list-item')
				.find_element_by_css_selector('.list-id').text=='hello')

		def tearDown(self):
			self.driver.close()

