from frappe.utils.selenium_testdriver import TestDriver
import unittest

class TestLogin(unittest.TestCase):
	def setUp(self):
		self.driver = TestDriver()

	def test_login(self):
		self.driver.login()

	def tearDown(self):
		self.driver.close()
