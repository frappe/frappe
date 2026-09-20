# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.installer import install_app
from frappe.tests import IntegrationTestCase

FAKE_APP = "abc_test_install_app"
FAKE_PATCHES = [
	"abc_test_install_app.patches.v1_0.fake_patch_one",
	"abc_test_install_app.patches.v1_0.fake_patch_two",
]

install_hook_calls = []


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

	def fake_get_hooks(hook=None, default="_KEEP_DEFAULT_LIST", app_name=None):
		if app_name == FAKE_APP:
			return frappe._dict({"after_install": [after_install]})
		return real_get_hooks(hook, default, app_name)

	def fake_get_patches_from_app(app, patch_type=None):
		if app == FAKE_APP:
			return FAKE_PATCHES
		return real_get_patches_from_app(app, patch_type)

	with (
		patch.object(frappe, "get_hooks", fake_get_hooks),
		patch.object(frappe, "get_all_apps", lambda *a, **kw: [*real_get_all_apps(*a, **kw), FAKE_APP]),
		patch.object(frappe, "setup_module_map"),
		patch("frappe.model.sync.sync_for"),
		patch("frappe.installer.add_module_defs"),
		patch("frappe.installer.add_to_installed_apps"),
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
