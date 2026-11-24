# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.installer import (
	add_module_defs,
	install_app,
	is_required_by,
	parse_required_app_name,
	remove_from_installed_apps,
)
from frappe.tests import IntegrationTestCase, UnitTestCase

# an app that is not on the bench, so no remote can name it
FAKE_APP = "zzz_test_app"
FAKE_PATCHES = [
	"zzz_test_app.patches.v1_0.fake_patch_one",
	"zzz_test_app.patches.v1_0.fake_patch_two",
]

install_hook_calls = []


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


class AfterInstallFailure(Exception):
	pass


def record_after_install():
	install_hook_calls.append("after_install_ok")


def fail_after_install():
	install_hook_calls.append("after_install_failing")
	raise AfterInstallFailure("after_install failed")


@contextmanager
def install_fake_app(after_install: str):
	from frappe.modules.patch_handler import get_patches_from_app as real_get_patches_from_app

	real_get_hooks = frappe.get_hooks
	real_get_all_apps = frappe.get_all_apps
	real_get_installed_apps = frappe.get_installed_apps

	def fake_get_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if app_name == FAKE_APP:
			return frappe._dict({"after_install": [after_install]})
		return real_get_hooks(hook, default, app_name)

	def fake_get_patches_from_app(app, patch_type=None):
		if app == FAKE_APP:
			return FAKE_PATCHES
		return real_get_patches_from_app(app, patch_type)

	def installed_apps_on_bench(*, _ensure_on_bench=False):
		apps = real_get_installed_apps()
		if _ensure_on_bench:
			on_bench = real_get_all_apps()
			apps = [app for app in apps if app in on_bench]
		return apps

	with (
		patch.object(frappe, "get_hooks", fake_get_hooks),
		patch.object(frappe, "get_all_apps", lambda *a, **kw: [*real_get_all_apps(*a, **kw), FAKE_APP]),
		patch.object(frappe, "get_installed_apps", installed_apps_on_bench),
		patch.object(frappe, "setup_module_map"),
		patch("frappe.model.sync.sync_for"),
		patch("frappe.installer.add_module_defs"),
		patch("frappe.installer.sync_dashboards"),
		patch("frappe.core.doctype.scheduled_job_type.scheduled_job_type.sync_jobs"),
		patch("frappe.utils.fixtures.sync_fixtures"),
		patch("frappe.modules.utils.sync_customizations"),
		patch("frappe.modules.patch_handler.get_patches_from_app", fake_get_patches_from_app),
	):
		yield


class TestInstallAppOrdering(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		install_hook_calls.clear()
		frappe.set_user("Administrator")
		self.addCleanup(self.delete_fake_patch_log_rows)
		self.addCleanup(self.uninstall_fake_app)

	def uninstall_fake_app(self):
		frappe.flags.in_install = False
		remove_from_installed_apps(FAKE_APP)

	def delete_fake_patch_log_rows(self):
		frappe.db.delete("Patch Log", {"patch": ["in", FAKE_PATCHES]})
		frappe.db.commit()  # nosemgrep

	def stamped_fake_patches(self) -> set[str]:
		return set(frappe.get_all("Patch Log", filters={"patch": ["in", FAKE_PATCHES]}, pluck="patch"))

	def test_after_install_success_marks_patches_complete(self):
		with install_fake_app(after_install=f"{__name__}.record_after_install"):
			install_app(FAKE_APP)

		self.assertEqual(install_hook_calls, ["after_install_ok"])
		self.assertEqual(self.stamped_fake_patches(), set(FAKE_PATCHES))

	def test_after_install_failure_leaves_patches_incomplete(self):
		with install_fake_app(after_install=f"{__name__}.fail_after_install"):
			with self.assertRaises(AfterInstallFailure):
				install_app(FAKE_APP)

		self.assertEqual(install_hook_calls, ["after_install_failing"])
		self.assertEqual(self.stamped_fake_patches(), set())

	def test_failed_install_can_be_retried(self):
		with install_fake_app(after_install=f"{__name__}.fail_after_install"):
			with self.assertRaises(AfterInstallFailure):
				install_app(FAKE_APP)

		self.assertNotIn(FAKE_APP, frappe.get_installed_apps())

		with install_fake_app(after_install=f"{__name__}.record_after_install"):
			install_app(FAKE_APP)

		self.assertEqual(install_hook_calls, ["after_install_failing", "after_install_ok"])
		self.assertIn(FAKE_APP, frappe.get_installed_apps())
		self.assertEqual(self.stamped_fake_patches(), set(FAKE_PATCHES))

	def test_failed_forced_reinstall_keeps_the_app_installed(self):
		with install_fake_app(after_install=f"{__name__}.record_after_install"):
			install_app(FAKE_APP)

		with install_fake_app(after_install=f"{__name__}.fail_after_install"):
			with self.assertRaises(AfterInstallFailure):
				install_app(FAKE_APP, force=True)

		self.assertIn(FAKE_APP, frappe.get_installed_apps())

	def test_retry_after_patches_were_stamped_stamps_each_patch_once(self):
		with install_fake_app(after_install=f"{__name__}.record_after_install"):
			with patch("frappe.utils.fixtures.sync_fixtures", side_effect=RuntimeError):
				with self.assertRaises(RuntimeError):
					install_app(FAKE_APP)

			install_app(FAKE_APP)

		self.assertCountEqual(
			frappe.get_all("Patch Log", filters={"patch": ["in", FAKE_PATCHES]}, pluck="patch"),
			FAKE_PATCHES,
		)


class TestAddModuleDefs(IntegrationTestCase):
	def test_skips_modules_the_app_already_has(self):
		modules = frappe.get_all("Module Def", {"app_name": "frappe", "custom": 0}, pluck="name")

		add_module_defs("frappe")

		self.assertCountEqual(
			frappe.get_all("Module Def", {"app_name": "frappe", "custom": 0}, pluck="name"), modules
		)
