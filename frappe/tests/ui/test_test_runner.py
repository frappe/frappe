from __future__ import print_function
from frappe.utils.selenium_testdriver import TestDriver
import unittest, os, frappe, time

class TestTestRunner(unittest.TestCase):
	def test_test_runner(self):
		driver = TestDriver()
		driver.login()
		for test in get_tests():
			if test.startswith('#'):
				continue

			timeout = 60
			if '#' in test:
				test, comment = test.split('#')
				test = test.strip()
				if comment.strip()=='long':
					timeout = 240

			print('Running {0}...'.format(test))

			frappe.db.set_value('Test Runner', None, 'module_path', test)
			frappe.db.commit()
			driver.refresh()
			driver.set_route('Form', 'Test Runner')
			driver.click_primary_action()
			driver.wait_for('#frappe-qunit-done', timeout=timeout)
			console = driver.get_console()
			if frappe.flags.tests_verbose or True:
				for line in console:
					print(line)
			print('-' * 40)
			print('Checking if passed "{0}"'.format(test))
			self.assertTrue('Tests Passed' in console)
			time.sleep(1)
		driver.close()

def get_tests():
	'''Get tests base on flag'''
	frappe.db.set_value('Test Runner', None, 'app', frappe.flags.ui_test_app or '')

	if frappe.flags.ui_test_path:
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

def get_tests_for(app):
	'''Get all tests for a particular app'''
	tests = []
	tests_path = frappe.get_app_path(app, 'tests', 'ui', 'tests.txt')
	if os.path.exists(tests_path):
		with open(tests_path, 'r') as fileobj:
			tests = fileobj.read().strip().splitlines()
	return tests

