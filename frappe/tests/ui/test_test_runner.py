from __future__ import print_function, unicode_literals
from frappe.utils.selenium_testdriver import TestDriver
import unittest, os, frappe, time

class TestTestRunner(unittest.TestCase):
	def test_test_runner(self):
		if frappe.flags.run_setup_wizard_ui_test:
			for setup_wizard_test in frappe.get_hooks("setup_wizard_test"):
				passed = frappe.get_attr(setup_wizard_test)()
				self.assertTrue(passed)
			return

		driver = TestDriver()
		frappe.db.set_default('in_selenium', '1')
		driver.login()
		for test in get_tests():
			if test.startswith('#'):
				continue

			timeout = 60
			passed = False
			if '#' in test:
				test, comment = test.split('#')
				test = test.strip()
				if comment.strip()=='long':
					timeout = 300

			print('Running {0}...'.format(test))

			frappe.db.set_value('Test Runner', None, 'module_path', test)
			frappe.db.commit()
			driver.refresh()
			driver.set_route('Form', 'Test Runner')
			try:
				driver.click_primary_action()
				driver.wait_for('#frappe-qunit-done', timeout=timeout)
				console = driver.get_console()
				passed  = 'Tests Passed' in console
			finally:
				console = driver.get_console()
				passed  = 'Test Passed' in console
				if frappe.flags.tests_verbose or not passed:
					for line in console:
						print(line)
					print('-' * 40)
				else:
					self.assertTrue(passed)
				time.sleep(1)
		frappe.db.set_default('in_selenium', None)
		driver.close()

def get_tests():
	'''Get tests base on flag'''
	frappe.db.set_value('Test Runner', None, 'app', frappe.flags.ui_test_app or '')

	if frappe.flags.ui_test_list:
		# list of tests
		return get_tests_for(test_list=frappe.flags.ui_test_list)
	elif frappe.flags.ui_test_path:
		# specific test
		return (frappe.flags.ui_test_path,)
	elif frappe.flags.ui_test_app:
		# specific app
		return get_tests_for(frappe.flags.ui_test_app)
	else:
		# all apps
		tests = []
		for app in frappe.get_installed_apps():
			tests.extend(get_tests_for(app))
		return tests

def get_tests_for(app=None, test_list=None):
	tests = []
	if test_list:
		# Get all tests from a particular txt file
		app, test_list = test_list.split(os.path.sep, 1)
		tests_path = frappe.get_app_path(app, test_list)
	else:
		# Get all tests for a particular app
		tests_path = frappe.get_app_path(app, 'tests', 'ui', 'tests.txt')
	if os.path.exists(tests_path):
		with open(tests_path, 'r') as fileobj:
			tests = fileobj.read().strip().splitlines()
	return tests
