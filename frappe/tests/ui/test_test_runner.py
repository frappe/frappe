from __future__ import print_function
from frappe.utils.selenium_testdriver import TestDriver
import unittest

class TestLogin(unittest.TestCase):
	def setUp(self):
		self.driver = TestDriver()

	def test_test_runner(self):
		self.driver.login()
		self.driver.set_route('Form', 'Test Runner')
		self.driver.click_primary_action()
		self.driver.wait_for('#qunit-testresult-display', timeout=60)
		self.driver.print_console()

	def tearDown(self):
		self.driver.close()
