# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import functools
import inspect
from unittest.mock import patch

import frappe
from frappe.public_api import (
	PublicAPIContractError,
	PublicAPISpec,
	get_public_spec,
	iter_public_apis,
	public,
)
from frappe.tests import UnitTestCase

try:
	import docstring_parser
except ImportError:
	docstring_parser = None


class PublicAPITestCase(UnitTestCase):
	def whitelist(self, fn):
		"""Whitelist a test function and deregister it on test teardown."""
		wrapped = frappe.whitelist()(fn)
		self.addCleanup(frappe.whitelisted.discard, wrapped)
		self.addCleanup(frappe.allowed_http_methods_for_whitelisted_func.pop, wrapped, None)
		return wrapped


class TestPublicDecorator(PublicAPITestCase):
	def test_valid_public_api(self):
		@public(group="Tests")
		@self.whitelist
		def endpoint(name: str, count: int = 0) -> dict:
			"""Do something for tests.

			:param name: Some name.
			:param count: Some count.
			:return: Some dict.
			"""
			return {}

		spec = endpoint.__public_api__
		self.assertIsInstance(spec, PublicAPISpec)
		self.assertEqual(spec.group, "Tests")
		self.assertIsNone(spec.deprecated)

	def test_returns_same_function_object(self):
		@self.whitelist
		def endpoint() -> None:
			"""Do nothing."""

		decorated = public()(endpoint)
		self.assertIs(decorated, endpoint)

	def test_not_whitelisted_fails(self):
		def endpoint() -> None:
			"""Do nothing."""

		with self.assertRaises(PublicAPIContractError) as ctx:
			public()(endpoint)
		self.assertIn("not whitelisted", str(ctx.exception))

	def test_missing_param_annotation_fails(self):
		@self.whitelist
		def endpoint(name, count: int = 0) -> None:
			"""Do nothing.

			:param name: Some name.
			:param count: Some count.
			"""

		with self.assertRaises(PublicAPIContractError) as ctx:
			public()(endpoint)
		self.assertIn("'name'", str(ctx.exception))
		self.assertNotIn("'count'", str(ctx.exception))

	def test_missing_return_annotation_fails(self):
		@self.whitelist
		def endpoint(name: str):
			"""Do nothing.

			:param name: Some name.
			"""

		with self.assertRaises(PublicAPIContractError) as ctx:
			public()(endpoint)
		self.assertIn("return type", str(ctx.exception))

	def test_missing_docstring_fails(self):
		@self.whitelist
		def endpoint() -> None:
			pass

		with self.assertRaises(PublicAPIContractError) as ctx:
			public()(endpoint)
		self.assertIn("docstring", str(ctx.exception))

	def test_self_and_cls_exempt_from_annotations(self):
		class Controller:
			@public()
			@self.whitelist
			def endpoint(self) -> None:
				"""Do nothing."""

		self.assertIsInstance(inspect.getattr_static(Controller, "endpoint").__public_api__, PublicAPISpec)

	def test_all_violations_reported_together(self):
		def endpoint(name):
			pass

		with self.assertRaises(PublicAPIContractError) as ctx:
			public()(endpoint)
		message = str(ctx.exception)
		self.assertIn("not whitelisted", message)
		self.assertIn("'name'", message)
		self.assertIn("return type", message)
		self.assertIn("docstring", message)

	def test_production_only_warns(self):
		def endpoint() -> None:
			pass

		with (
			patch.object(frappe, "in_test", False),
			patch.object(frappe, "_dev_server", 0),
			patch.dict("os.environ", {"CI": ""}),
		):
			with self.assertWarns(UserWarning):
				decorated = public()(endpoint)

		# marking still happens in production, only enforcement is relaxed
		self.assertIsInstance(decorated.__public_api__, PublicAPISpec)


class TestPublicSpecDiscovery(PublicAPITestCase):
	def test_get_public_spec_walks_wrapped_chain(self):
		@public(group="Tests")
		@self.whitelist
		def endpoint() -> None:
			"""Do nothing."""

		@functools.wraps(endpoint)
		def conforming_wrapper():
			return endpoint()

		# functools.wraps copies __dict__, so the attribute is already there
		self.assertIsNotNone(get_public_spec(conforming_wrapper))

		def nonconforming_wrapper():
			return endpoint()

		nonconforming_wrapper.__wrapped__ = endpoint

		self.assertIsNotNone(get_public_spec(nonconforming_wrapper))
		self.assertIsNone(get_public_spec(lambda: None))

	def test_iter_public_apis(self):
		@public(group="Tests")
		@self.whitelist
		def endpoint() -> None:
			"""Do nothing."""

		matches = [(fn, spec) for fn, spec in iter_public_apis() if fn is endpoint]
		self.assertEqual(len(matches), 1)
		self.assertEqual(matches[0][1].group, "Tests")


class TestPublicAPIDocstringLint(UnitTestCase):
	"""Linter for `@frappe.public` docstrings — Sphinx style, enforced in CI.

	This test iterates every registered public API (from any installed app
	whose modules are imported), so apps inherit the check via standard test
	discovery without any runtime cost.
	"""

	def test_public_api_docstrings(self):
		if docstring_parser is None:
			self.skipTest("docstring_parser is not installed (frappe[test] extra)")

		violations = []
		for fn, _spec in iter_public_apis():
			violations.extend(self.check_docstring(fn))

		if violations:
			self.fail("Public API docstring violations:\n" + "\n".join(f"  - {v}" for v in violations))

	def check_docstring(self, fn) -> list[str]:
		fn_path = f"{fn.__module__}.{getattr(fn, '__qualname__', fn.__name__)}"
		doc = inspect.getdoc(fn) or ""
		lines = doc.splitlines()

		if not lines or not lines[0].strip():
			return [f"{fn_path}: docstring must start with a one-line summary"]

		violations = []
		if len(lines) > 1 and lines[1].strip():
			violations.append(f"{fn_path}: summary line must be followed by a blank line")

		try:
			parsed = docstring_parser.parse(doc, style=docstring_parser.DocstringStyle.REST)
		except docstring_parser.ParseError as e:
			return [*violations, f"{fn_path}: docstring failed to parse as Sphinx style ({e})"]

		param_names = set(inspect.signature(fn).parameters)
		for param in parsed.params:
			if param.arg_name not in param_names:
				violations.append(f"{fn_path}: :param {param.arg_name}: does not match any parameter")
			if param.type_name:
				violations.append(
					f"{fn_path}: :param {param.arg_name}: must not declare a type"
					" — types belong in annotations"
				)

		return violations
