# The `shell_hooks` boot key: the apps that ship a `shell.js` and whose gate lets this session run it.

import os
import shutil
import tempfile
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.shell.boot import KEY_BUDGET, core_boot
from frappe.shell.shell_hooks import CACHE_KEY, hooked_apps, shell_hooks
from frappe.tests import IntegrationTestCase
from frappe.utils import orjson_dumps

ALLOW = "frappe.tests.test_shell_hooks.allow"
REFUSE = "frappe.tests.test_shell_hooks.refuse"
RAISE = "frappe.tests.test_shell_hooks.explode"


def allow():
	return True


def refuse():
	return False


def explode():
	raise RuntimeError("the app's gate broke")


class TestShellHooks(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")
		frappe.client_cache.delete_value(CACHE_KEY)
		self.addCleanup(frappe.client_cache.delete_value, CACHE_KEY)
		self.addCleanup(frappe.set_user, "Administrator")

	def test_a_site_with_no_hooked_app_runs_no_check(self):
		with (
			patch("frappe.shell.shell_hooks.hooked_apps", return_value=[]),
			patch("frappe.shell.shell_hooks.may_run") as may_run,
		):
			self.assertEqual(core_boot()["shell_hooks"], [])

		may_run.assert_not_called()

	def test_the_apps_screen_check_decides(self):
		screens = {"allowed": ALLOW, "refused": REFUSE}
		with hooked(screens):
			self.assertEqual(shell_hooks(["frappe", "refused", "allowed"]), ["allowed"])

	def test_the_list_follows_the_app_order(self):
		with hooked({"first": ALLOW, "second": ALLOW}):
			self.assertEqual(shell_hooks(["second", "first"]), ["second", "first"])

	def test_a_hooked_app_the_site_lacks_is_not_listed(self):
		with hooked({"elsewhere": ALLOW}):
			self.assertEqual(shell_hooks(["frappe"]), [])

	def test_a_raising_check_fails_closed_and_is_logged(self):
		with hooked({"broken": RAISE}), patch("frappe.log_error") as log_error:
			self.assertEqual(shell_hooks(["broken"]), [])

		log_error.assert_called_once_with(title="add_to_apps_screen has_permission failed for broken")

	def test_no_apps_screen_check_falls_back_to_the_prefix_gate(self):
		with hooked({"frappe": None}):
			self.assertEqual(shell_hooks(["frappe"]), ["frappe"])

			frappe.set_user("Guest")
			self.assertEqual(shell_hooks(["frappe"]), [])

	def test_the_hooked_apps_are_cached_outside_developer_mode(self):
		with (
			patch.dict(frappe.conf, {"developer_mode": 0}),
			patch("frappe.shell.shell_hooks.hooked_apps", return_value=[]) as glob,
		):
			shell_hooks(["frappe"])
			shell_hooks(["frappe"])
		glob.assert_called_once()

	def test_developer_mode_reads_the_disk_on_each_boot(self):
		with (
			patch.dict(frappe.conf, {"developer_mode": 1}),
			patch("frappe.shell.shell_hooks.hooked_apps", return_value=[]) as glob,
		):
			shell_hooks(["frappe"])
			shell_hooks(["frappe"])
		self.assertEqual(glob.call_count, 2)

	def test_the_key_is_within_the_boot_key_budget(self):
		with hooked({"frappe": None}):
			listed = core_boot()["shell_hooks"]

		self.assertEqual(listed, ["frappe"])
		self.assertLess(len(orjson_dumps(listed, decode=False)), KEY_BUDGET)


class TestHookedApps(IntegrationTestCase):
	def test_an_app_ships_a_hook_at_module_frontend_shell_js(self):
		root = tempfile.mkdtemp(prefix="shell-hooks-")
		self.addCleanup(shutil.rmtree, root)
		write(root, "hooked/fcrm/frontend/shell.js")
		write(root, "unhooked/fcrm/frontend/acts.js")
		write(root, "deep/fcrm/doctype/crm_deal/frontend/shell.js")

		with (
			patch("frappe.get_installed_apps", return_value=["hooked", "unhooked", "deep"]),
			patch("frappe.get_app_path", side_effect=lambda app: os.path.join(root, app)),
		):
			self.assertEqual(hooked_apps(), ["hooked"])


@contextmanager
def hooked(screens: dict[str, str | None]):
	"""`screens` as the hooked apps, each with that `has_permission`, or no apps-screen entry for None."""
	get_hooks = frappe.get_hooks

	def fake_hooks(hook=None, *args, **kwargs):
		app = kwargs.get("app_name")
		if hook == "add_to_apps_screen" and app in screens:
			check = screens[app]
			return [{"name": app, "has_permission": check}] if check else []
		return get_hooks(hook, *args, **kwargs)

	with (
		patch("frappe.shell.shell_hooks.hooked_apps", return_value=list(screens)),
		patch("frappe.get_hooks", side_effect=fake_hooks),
	):
		yield


def write(root: str, path: str):
	full = os.path.join(root, path)
	os.makedirs(os.path.dirname(full), exist_ok=True)
	with open(full, "w") as f:
		f.write("export function setup() {}\n")
