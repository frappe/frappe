import os
import sys
import unittest
from types import ModuleType
from unittest.mock import patch

from frappe.testing.config import TestConfig, TestParameters
from frappe.testing.discovery import _add_module_tests
from frappe.testing.loader import FrappeTestLoader
from frappe.testing.runner import TestRunner
from frappe.tests.utils.test_capabilities import (
	TestService,
	apply_test_service_skips,
	get_required_test_services,
	is_test_service_available,
	requires_selected_test_service,
	requires_test_service,
)


class TestTestCapabilities(unittest.TestCase):
	def test_services_are_available_by_default(self):
		with patch.dict(os.environ, {}, clear=True):
			self.assertTrue(is_test_service_available(TestService.WEB_SERVER))
			self.assertTrue(is_test_service_available(TestService.BACKGROUND_WORKER))

	def test_service_can_be_disabled_with_environment_variable(self):
		with patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "0"}, clear=True):
			self.assertFalse(is_test_service_available(TestService.WEB_SERVER))

	def test_service_accepts_explicit_true_value(self):
		with patch.dict(os.environ, {"FRAPPE_TEST_BACKGROUND_WORKER": "yes"}, clear=True):
			self.assertTrue(is_test_service_available(TestService.BACKGROUND_WORKER))

	def test_invalid_service_value_fails_loudly(self):
		with patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "sometimes"}, clear=True):
			with self.assertRaisesRegex(ValueError, "FRAPPE_TEST_WEB_SERVER"):
				is_test_service_available(TestService.WEB_SERVER)

	def test_required_service_marks_test_as_skipped_when_unavailable(self):
		with patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "off"}, clear=True):

			@requires_test_service(TestService.WEB_SERVER)
			def web_test():
				pass

		self.assertTrue(web_test.__unittest_skip__)
		self.assertEqual(web_test.__unittest_skip_why__, "Requires a running Frappe test web server.")
		self.assertEqual(get_required_test_services(web_test), {TestService.WEB_SERVER})

	def test_cli_service_name_is_converted_to_enum(self):
		self.assertEqual(TestService.from_cli_name("web-server"), TestService.WEB_SERVER)
		with self.assertRaisesRegex(ValueError, "web-server, background-worker"):
			TestService.from_cli_name("unknown")

	def test_required_services_are_collected_from_method_and_class(self):
		with patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "1", "FRAPPE_TEST_BACKGROUND_WORKER": "1"}):

			@requires_test_service(TestService.BACKGROUND_WORKER)
			class ServiceTest(unittest.TestCase):
				@requires_test_service(TestService.WEB_SERVER)
				def test_service(self):
					pass

		test = ServiceTest("test_service")
		self.assertEqual(
			get_required_test_services(test),
			{TestService.BACKGROUND_WORKER, TestService.WEB_SERVER},
		)
		self.assertTrue(requires_selected_test_service(test, TestService.WEB_SERVER))
		self.assertTrue(requires_selected_test_service(test, TestService.BACKGROUND_WORKER))
		self.assertTrue(requires_selected_test_service(test, None))

	def test_module_can_declare_required_services(self):
		module = sys.modules[__name__]
		with patch.object(
			module,
			"required_test_services",
			frozenset({TestService.WEB_SERVER}),
			create=True,
		):
			test = self.__class__("test_module_can_declare_required_services")
			self.assertEqual(get_required_test_services(test), {TestService.WEB_SERVER})

	def test_module_service_is_skipped_when_unavailable(self):
		module = sys.modules[__name__]
		with (
			patch.object(
				module,
				"required_test_services",
				frozenset({TestService.WEB_SERVER}),
				create=True,
			),
			patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "0"}),
		):
			test = self.__class__("test_module_service_is_skipped_when_unavailable")
			apply_test_service_skips(test)
			result = unittest.TestResult()
			test.run(result)

		self.assertEqual(result.testsRun, 1)
		self.assertEqual(len(result.skipped), 1)

	def test_standard_and_light_loaders_filter_by_required_service(self):
		module_name = "frappe.tests._test_service_filter_fixture"
		module = ModuleType(module_name)

		with patch.dict(os.environ, {"FRAPPE_TEST_WEB_SERVER": "1"}):

			@requires_test_service(TestService.WEB_SERVER)
			class WebTest(unittest.TestCase):
				def test_web(self):
					pass

		class PlainTest(unittest.TestCase):
			def test_plain(self):
				pass

		WebTest.__module__ = module_name
		PlainTest.__module__ = module_name
		module.WebTest = WebTest
		module.PlainTest = PlainTest

		with patch.dict(sys.modules, {module_name: module}):
			runner = TestRunner(cfg=TestConfig(test_service=TestService.WEB_SERVER))
			_add_module_tests(runner, "frappe", module_name)
			standard_suite = runner.per_app_categories["frappe"]["unspecified-category"]

			light_loader = FrappeTestLoader()
			light_loader.params = TestParameters(test_service=TestService.WEB_SERVER)
			light_loader.testsuite = unittest.TestSuite()
			light_loader.recursive_load_suites_in_pymodule(unittest.TestLoader().loadTestsFromModule(module))

		self.assertEqual(standard_suite.countTestCases(), 1)
		self.assertEqual(light_loader.testsuite.countTestCases(), 1)