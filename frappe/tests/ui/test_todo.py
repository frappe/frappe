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

		time.sleep(3)

		self.driver.print_console()

		result_list = self.driver.get_visible_element('.result-list')
		first_element_text = (result_list
			.find_element_by_css_selector('.list-item')
			.find_element_by_css_selector('.list-id').text)

		self.assertTrue('hello' in first_element_text)

	def tearDown(self):
		self.driver.close()
