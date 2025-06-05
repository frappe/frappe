import importlib
import unittest
from collections import deque
from pathlib import Path

import frappe
from frappe.modules.utils import get_module_name
from frappe.testing.config import TestParameters


class FrappeTestLoader(unittest.TestLoader):
	def recursive_load_suites_in_pymodule(self, suite):
		suites_queue = deque([suite])
		while suites_queue:
			suite = suites_queue.popleft()
			for elem in suite:
				if elem.countTestCases():
					if isinstance(elem, unittest.TestSuite):
						suites_queue.append(elem)
					elif isinstance(elem, unittest.TestCase):
						if self.params.tests:
							if elem._testMethodName in self.params.tests:
								self.testsuite.addTest(elem)
						else:
							self.testsuite.addTest(elem)

	def load_testsuites_in_pymodule(self, file_modules):
		for module in file_modules:
			suite = self.loadTestsFromModule(module)
			self.recursive_load_suites_in_pymodule(suite)

	def load_pymodule_for_files(self, files: list):
		"""
		files: list of tuple of (Path, str)
		"""
		_file_modules = []
		for app_path, test_file in files:
			module_name = f"{'.'.join(test_file.relative_to(app_path.parent).parent.parts)}.{test_file.stem}"
			module = importlib.import_module(module_name)
			_file_modules.append(module)
		return _file_modules

	def get_files(self, apps: list) -> list:
		files = []
		for app in apps:
			app_path = Path(frappe.get_app_path(app))
			for test_file in app_path.glob("**/test_*.py"):
				files.append((app_path, test_file))
		return files

	def discover_tests(self, params: TestParameters) -> unittest.TestSuite:
		self.params = params
		self.testsuite = unittest.TestSuite()

		if self.params.tests:
			# handle --test; highest priority; will ignore --doctype and --app
			files = self.get_files(frappe.get_installed_apps())
			file_pymodules = self.load_pymodule_for_files(files)
			self.load_testsuites_in_pymodule(file_pymodules)

		elif self.params.doctype:
			# handle --doctype; will ignore --app
			module = frappe.get_cached_value("DocType", self.params.doctype, "module")
			app = frappe.get_cached_value("Module Def", module, "app_name")
			pymodule_name = get_module_name(self.params.doctype, module, "test_", app=app)
			pymodule = importlib.import_module(pymodule_name)
			self.load_testsuites_in_pymodule([pymodule])

		elif self.params.app:
			# handle --app
			files = self.get_files([self.params.app])
			file_pymodules = self.load_pymodule_for_files(files)
			self.load_testsuites_in_pymodule(file_pymodules)

		elif self.params.module:
			# handle --module; supports --test as well
			pymodule = importlib.import_module(self.params.module)
			self.load_testsuites_in_pymodule([pymodule])

		return self.testsuite
