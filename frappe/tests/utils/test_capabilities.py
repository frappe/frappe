import os
import sys
import unittest
from enum import StrEnum
from functools import wraps
from types import ModuleType
from typing import TypeVar

TestTarget = TypeVar("TestTarget")


_REQUIRED_TEST_SERVICES_ATTRIBUTE = "__frappe_required_test_services__"
_MODULE_REQUIRED_TEST_SERVICES_ATTRIBUTE = "required_test_services"


class TestService(StrEnum):
	"""Services that may be deliberately absent from a test environment."""

	WEB_SERVER = "web server"
	BACKGROUND_WORKER = "background worker"

	@property
	def cli_name(self) -> str:
		return self.name.lower().replace("_", "-")

	@classmethod
	def from_cli_name(cls, value: str) -> "TestService":
		try:
			return cls[value.upper().replace("-", "_")]
		except KeyError as error:
			valid_names = ", ".join(service.cli_name for service in cls)
			raise ValueError(f"Unknown test service {value!r}. Choose from: {valid_names}.") from error


_SERVICE_ENVIRONMENT_VARIABLE = {
	TestService.WEB_SERVER: "FRAPPE_TEST_WEB_SERVER",
	TestService.BACKGROUND_WORKER: "FRAPPE_TEST_BACKGROUND_WORKER",
}
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def is_test_service_available(service: TestService) -> bool:
	"""Return whether ``service`` is available to this test process.
	Services are available by default so existing local and MariaDB test runs keep their current behaviour.  CI can opt out with the corresponding
	``FRAPPE_TEST_*`` environment variable.
	"""
	try:
		environment_variable = _SERVICE_ENVIRONMENT_VARIABLE[service]
	except KeyError as error:
		raise ValueError(f"Unknown test service: {service!r}") from error

	value = os.environ.get(environment_variable)
	if value is None:
		return True

	normalized_value = value.strip().lower()
	if normalized_value in _TRUE_VALUES:
		return True
	if normalized_value in _FALSE_VALUES:
		return False

	valid_values = ", ".join(sorted(_TRUE_VALUES | _FALSE_VALUES))
	raise ValueError(f"{environment_variable} must be one of {valid_values}; received {value!r}.")


def requires_test_service(service: TestService):
	"""Mark a test's required service and skip it when that service is unavailable."""
	if not isinstance(service, TestService):
		raise TypeError(f"service must be a TestService, received {service!r}")

	def decorator(test: TestTarget) -> TestTarget:
		required_services = set(getattr(test, _REQUIRED_TEST_SERVICES_ATTRIBUTE, ()))
		required_services.add(service)
		setattr(test, _REQUIRED_TEST_SERVICES_ATTRIBUTE, frozenset(required_services))
		return unittest.skipUnless(
			is_test_service_available(service), f"Requires a running Frappe test {service.value}."
		)(test)

	return decorator


def get_required_test_services(test: object) -> frozenset[TestService]:
	"""Return services declared on a test method, class, or module."""
	targets: list[object] = [test]
	if isinstance(test, unittest.TestCase):
		test_class = test.__class__
		module = sys.modules.get(test_class.__module__)
		if module:
			targets.append(module)
		targets.extend((test_class, getattr(test_class, test._testMethodName)))

	required_services: set[TestService] = set()
	for target in targets:
		attribute = (
			_MODULE_REQUIRED_TEST_SERVICES_ATTRIBUTE
			if isinstance(target, ModuleType)
			else _REQUIRED_TEST_SERVICES_ATTRIBUTE
		)
		for service in getattr(target, attribute, ()):
			if not isinstance(service, TestService):
				raise TypeError(f"Required test services must be TestService values, received {service!r}")
			required_services.add(service)

	return frozenset(required_services)


def requires_selected_test_service(test: object, service: TestService | None) -> bool:
	"""Return whether a test matches an optional required-service filter."""
	return service is None or service in get_required_test_services(test)


def apply_test_service_skips(test: unittest.TestCase) -> None:
	"""Skip a loaded test when any service it declares is unavailable."""
	unavailable_services = [
		service for service in get_required_test_services(test) if not is_test_service_available(service)
	]
	if not unavailable_services:
		return

	test_method = getattr(test, test._testMethodName)

	@wraps(test_method)
	def skipped_test_method():
		return test_method()

	service_names = ", ".join(sorted(service.value for service in unavailable_services))
	setattr(
		test,
		test._testMethodName,
		unittest.skip(f"Requires running Frappe test services: {service_names}.")(skipped_test_method),
	)
