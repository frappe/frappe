# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from unittest.mock import patch

import frappe
from frappe.installer import is_required_by, parse_required_app_name
from frappe.tests import UnitTestCase

# an app that is not on the bench, so no remote can name it
FAKE_APP = "zzz_test_app"


class TestRequiredAppName(UnitTestCase):
	def test_every_spelling_of_a_requirement_resolves_to_the_app(self):
		requirements = [
			"erpnext",
			"frappe/erpnext",
			"frappe/erpnext@version-15",
			"https://github.com/frappe/erpnext.git",
			"https://github.com/frappe/erpnext.git#develop",
			"git@github.com:frappe/erpnext.git",
			"/home/frappe/frappe-bench/apps/erpnext/",
		]
		for requirement in requirements:
			with self.subTest(requirement=requirement):
				self.assertEqual(parse_required_app_name(requirement), "erpnext")

	def test_an_app_off_the_bench_resolves_without_a_remote_lookup(self):
		"""`parse_app_name` asks GitHub for a name it cannot place; a dependency check must not."""
		self.assertEqual(parse_required_app_name(FAKE_APP), FAKE_APP)


class TestIsRequiredBy(UnitTestCase):
	"""Guards the check that stops `remove_app` from uninstalling a dependency."""

	def requiring(self, *requirements):
		return patch.object(frappe, "get_hooks", lambda *a, **k: list(requirements))

	def test_an_app_a_qualified_requirement_names_is_a_dependency(self):
		with self.requiring("frappe/erpnext"):
			self.assertTrue(is_required_by("erpnext", "hrms"))

	def test_an_app_only_spelled_inside_a_requirement_is_not_a_dependency(self):
		"""`next` sits inside `frappe/erpnext` without being the app it names."""
		with self.requiring("frappe/erpnext"):
			self.assertFalse(is_required_by("next", "hrms"))

	def test_an_app_off_the_bench_is_matched_without_a_remote_lookup(self):
		with self.requiring(FAKE_APP):
			self.assertTrue(is_required_by(FAKE_APP, "frappe"))
