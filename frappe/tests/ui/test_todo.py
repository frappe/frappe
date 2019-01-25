from __future__ import print_function, unicode_literals
from __future__ import print_function
from frappe.utils.selenium_testdriver import TestDriver
import unittest
import time, os

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

		# refresh
		self.driver.click_secondary_action()

		time.sleep(2)

		result_list = self.driver.get_visible_element('.result-list')
		first_element_text = (result_list
			.find_element_by_css_selector('.list-item')
			.find_element_by_css_selector('.list-id').text)

		# if os.environ.get('CI'):
		# 	# we don't run this test in Travis as it always fails
		# 	# reinforcing why we use Unit Testing instead of integration
		# 	# testing
		# 	return

		self.assertTrue('hello' in first_element_text)

	def tearDown(self):
		self.driver.close()
