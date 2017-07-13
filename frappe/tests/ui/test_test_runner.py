from __future__ import print_function
from frappe.utils.selenium_testdriver import TestDriver
import unittest, os, frappe, time

class TestLogin(unittest.TestCase):
	def test_test_runner(self):
		for test in get_tests():
			print('Running {0}...'.format(test))
			frappe.db.set_value('Test Runner', None, 'module_path', test)
			frappe.db.commit()
			driver = TestDriver()
			driver.login()
			driver.set_route('Form', 'Test Runner')
			driver.click_primary_action()
			driver.wait_for('#frappe-qunit-done', timeout=60)
			console = driver.get_console()
			if frappe.flags.tests_verbose or True:
				for line in console:
					print(line)
			print('-' * 40)
			print('Checking if passed "{0}"'.format(test))
			self.assertTrue('Tests Passed' in console)
			driver.close()
			time.sleep(1)

def get_tests():
	'''Get tests base on flag'''
	if frappe.flags.ui_test_app:
		return get_tests_for(frappe.flags.ui_test_app)
	elif frappe.flags.ui_test_path:
		return (frappe.flags.ui_test_path,)
	else:
		tests = []
		for app in frappe.get_installed_apps():
			tests.extend(get_tests_for(app))
		return tests

def get_tests_for(app):
	'''Get all tests for a particular app'''
	tests = []
	tests_path = frappe.get_app_path(app, 'tests', 'ui')
	if os.path.exists(tests_path):
		for basepath, folders, files in os.walk(tests_path): # pylint: disable=unused-variable
			if os.path.join('ui', 'data') in basepath:
				continue

			for fname in files:
				if fname.startswith('test') and fname.endswith('.js'):
					path = os.path.join(basepath, fname)
					path = os.path.relpath(path, frappe.get_app_path(app))
					tests.append(os.path.join(app, path))

	return tests

