# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
import json
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.installer import (
	disable_app,
	enable_app,
	parse_required_app_name,
	reapply_disabled_app_state,
	remove_from_installed_apps,
	set_app_disabled,
)
from frappe.tests import IntegrationTestCase, UnitTestCase

FAKE_APP = "zzz_test_app"
# sits inside the requirement string `frappe/erpnext` without being the app it names
COLLIDING_APP = "next"

hook_calls = []


class HookFailure(Exception):
	pass


def record_before_disable():
	hook_calls.append("before_disable")


def record_after_disable():
	hook_calls.append("after_disable")


def record_before_enable():
	hook_calls.append("before_enable")


def record_after_enable():
	hook_calls.append("after_enable")


def record_disabled_apps():
	hook_calls.append(read_disabled_apps())


def fail():
	raise HookFailure("hook failed")


def read_disabled_apps() -> list[str]:
	"""Read the global from its row, past the defaults cache and the request cache."""
	table = frappe.qb.DocType("DefaultValue")
	rows = (
		frappe.qb.from_(table)
		.select(table.defvalue)
		.where((table.defkey == "disabled_apps") & (table.parent == "__global"))
		.run()
	)
	return json.loads(rows[0][0]) if rows and rows[0][0] else []


def write_disabled_apps(apps: list[str]):
	frappe.db.set_global("disabled_apps", json.dumps(apps))
	frappe.db.commit()  # nosemgrep
	frappe.clear_cache()
	frappe.client_cache.erase_persistent_caches()


@contextmanager
def fake_app(hooks: dict | None = None, name: str = FAKE_APP):
	"""Present `name` as an installed app, with only the hooks a test asks for.

	`hooks` maps `(app_name, hook)` to a value. Any other hook of the fake app is empty, and
	every other app keeps its real hooks. `get_installed_apps_info` is pinned to the real
	apps because it imports each app module to read a version.
	"""
	overrides = hooks or {}
	real_get_hooks = frappe.get_hooks
	installed = [*frappe.get_installed_apps(), name]
	apps_info = frappe.utils.get_installed_apps_info()

	def app_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if (app_name, hook) in overrides:
			return overrides[(app_name, hook)]
		if app_name == name:
			return []
		return real_get_hooks(hook, default, app_name)

	with (
		patch.object(frappe, "get_installed_apps", lambda *a, **k: installed),
		patch.object(frappe, "get_hooks", app_hooks),
		patch.object(frappe.utils, "get_installed_apps_info", lambda: apps_info),
	):
		yield


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


class TestAppToggle(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		hook_calls.clear()
		self.disabled_apps_before = read_disabled_apps()
		self.installed_apps_before = frappe.db.get_global("installed_apps")
		self.addCleanup(self.restore_globals)

	def restore_globals(self):
		"""A toggle commits, so put both globals back whatever the test did to them."""
		frappe.db.set_global("installed_apps", self.installed_apps_before)
		write_disabled_apps(self.disabled_apps_before)

	def test_disable_adds_to_disabled_apps(self):
		with fake_app():
			disable_app(FAKE_APP)

		self.assertIn(FAKE_APP, read_disabled_apps())
		self.assertIn(FAKE_APP, frappe.get_disabled_apps())
		self.assertNotIn(FAKE_APP, frappe.get_active_apps())

	def test_enable_removes_from_disabled_apps(self):
		write_disabled_apps([*self.disabled_apps_before, FAKE_APP])

		with fake_app():
			enable_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, read_disabled_apps())
		self.assertNotIn(FAKE_APP, frappe.get_disabled_apps())

	def test_disable_hooks_run_around_the_flip(self):
		hooks = {
			(FAKE_APP, "before_disable"): ["frappe.tests.test_app_toggle.record_before_disable"],
			(FAKE_APP, "after_disable"): ["frappe.tests.test_app_toggle.record_after_disable"],
		}
		with fake_app(hooks):
			disable_app(FAKE_APP)

		self.assertEqual(hook_calls, ["before_disable", "after_disable"])

	def test_enable_hooks_run_around_the_flip(self):
		write_disabled_apps([*self.disabled_apps_before, FAKE_APP])
		hooks = {
			(FAKE_APP, "before_enable"): ["frappe.tests.test_app_toggle.record_before_enable"],
			(FAKE_APP, "after_enable"): ["frappe.tests.test_app_toggle.record_after_enable"],
		}
		with fake_app(hooks):
			enable_app(FAKE_APP)

		self.assertEqual(hook_calls, ["before_enable", "after_enable"])

	def test_before_disable_runs_while_the_app_is_still_active(self):
		hooks = {(FAKE_APP, "before_disable"): ["frappe.tests.test_app_toggle.record_disabled_apps"]}
		with fake_app(hooks):
			disable_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, hook_calls[0])

	def test_after_disable_runs_once_the_app_is_inactive(self):
		hooks = {(FAKE_APP, "after_disable"): ["frappe.tests.test_app_toggle.record_disabled_apps"]}
		with fake_app(hooks):
			disable_app(FAKE_APP)

		self.assertIn(FAKE_APP, hook_calls[0])

	def test_failing_hook_leaves_the_database_unchanged(self):
		hooks = {(FAKE_APP, "after_disable"): ["frappe.tests.test_app_toggle.fail"]}
		with fake_app(hooks), self.assertRaises(HookFailure):
			disable_app(FAKE_APP)

		self.assertEqual(read_disabled_apps(), self.disabled_apps_before)

	def test_failing_hook_leaves_the_cache_unchanged(self):
		"""The flip is committed before the hooks, so a rollback has to drop the caches too."""
		hooks = {(FAKE_APP, "after_disable"): ["frappe.tests.test_app_toggle.fail"]}
		with fake_app(hooks), self.assertRaises(HookFailure):
			disable_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, frappe.get_disabled_apps())
		with self.secondary_connection():
			self.assertNotIn(FAKE_APP, frappe.get_disabled_apps())

	def test_a_hook_sees_the_flip_it_then_rolls_back(self):
		"""Guards the test above: the flip must reach the database before the hook fails."""
		hooks = {
			(FAKE_APP, "after_disable"): [
				"frappe.tests.test_app_toggle.record_disabled_apps",
				"frappe.tests.test_app_toggle.fail",
			]
		}
		with fake_app(hooks), self.assertRaises(HookFailure):
			disable_app(FAKE_APP)

		self.assertIn(FAKE_APP, hook_calls[0])
		self.assertEqual(read_disabled_apps(), self.disabled_apps_before)

	def test_cannot_disable_frappe(self):
		with self.assertRaises(frappe.ValidationError):
			disable_app("frappe")

		self.assertNotIn("frappe", read_disabled_apps())

	def test_cannot_disable_an_app_that_is_not_installed(self):
		with self.assertRaises(frappe.ValidationError):
			disable_app(FAKE_APP)

	def test_cannot_enable_an_app_that_is_not_installed(self):
		with self.assertRaises(frappe.ValidationError):
			enable_app(FAKE_APP)

	def test_cannot_disable_an_app_another_active_app_requires(self):
		hooks = {("frappe", "required_apps"): [FAKE_APP]}
		with fake_app(hooks), self.assertRaises(frappe.ValidationError):
			disable_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, read_disabled_apps())

	def test_cannot_disable_an_app_a_qualified_requirement_names(self):
		"""A `required_apps` entry may be spelled `org/repo`; the dependency is the repo."""
		hooks = {("frappe", "required_apps"): [f"frappe/{FAKE_APP}"]}
		with fake_app(hooks), self.assertRaises(frappe.ValidationError):
			disable_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, read_disabled_apps())

	def test_can_disable_an_app_whose_name_is_only_a_substring_of_a_requirement(self):
		"""`next` is inside `frappe/erpnext` but is not it, so it must not count as a dependency."""
		hooks = {("frappe", "required_apps"): ["frappe/erpnext"]}
		with fake_app(hooks, name=COLLIDING_APP):
			disable_app(COLLIDING_APP)

		self.assertIn(COLLIDING_APP, read_disabled_apps())

	def test_cannot_enable_an_app_whose_dependency_is_disabled(self):
		write_disabled_apps([*self.disabled_apps_before, FAKE_APP, "frappe"])
		hooks = {(FAKE_APP, "required_apps"): ["frappe"]}
		with fake_app(hooks), self.assertRaises(frappe.ValidationError):
			enable_app(FAKE_APP)

		self.assertIn(FAKE_APP, read_disabled_apps())

	def test_uninstall_clears_the_disabled_state(self):
		write_disabled_apps([*self.disabled_apps_before, FAKE_APP])

		with fake_app():
			remove_from_installed_apps(FAKE_APP)

		self.assertNotIn(FAKE_APP, read_disabled_apps())

	def test_reapply_runs_before_disable_again(self):
		write_disabled_apps([*self.disabled_apps_before, FAKE_APP])
		hooks = {(FAKE_APP, "before_disable"): ["frappe.tests.test_app_toggle.record_before_disable"]}
		with fake_app(hooks):
			reapply_disabled_app_state()

		self.assertEqual(hook_calls, ["before_disable"])
		self.assertIn(FAKE_APP, read_disabled_apps())

	def test_set_app_disabled_does_not_commit(self):
		"""The caller owns the commit, so the whole toggle can roll back as one unit."""
		set_app_disabled(FAKE_APP, True)
		self.assertIn(FAKE_APP, read_disabled_apps())

		frappe.db.rollback()
		self.assertNotIn(FAKE_APP, read_disabled_apps())
