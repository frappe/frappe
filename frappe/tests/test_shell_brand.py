# The `brand` of an app's `add_to_apps_screen` entry: site data over the entry's title and logo, and the app's tab icon.

from collections import defaultdict
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.shell.boot import get_boot, index_tiles
from frappe.shell.titles import app_brand, app_screen
from frappe.tests import IntegrationTestCase

BRAND = "frappe.tests.test_shell_brand.brand"
PARTIAL = "frappe.tests.test_shell_brand.partial_brand"
RAISE = "frappe.tests.test_shell_brand.explode"
LIST = "frappe.tests.test_shell_brand.a_list"
NON_STRING = "frappe.tests.test_shell_brand.non_string_logo"
COUNTED = "frappe.tests.test_shell_brand.counted_brand"


def brand():
	return {"title": "Acme Sales", "logo": "/files/acme.png", "favicon": "/files/acme-icon.png"}


def partial_brand():
	return {"favicon": "/files/acme-icon.png"}


def a_list():
	return ["Acme"]


def non_string_logo():
	return {"title": "Acme Sales", "logo": {"url": "/files/acme.png"}, "favicon": 7}


calls = []


def counted_brand():
	calls.append(1)
	return brand()


def explode():
	raise RuntimeError("the brand broke")


class TestShellBrand(IntegrationTestCase):
	def setUp(self):
		clear_request_cache()
		self.addCleanup(clear_request_cache)
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_an_app_without_a_brand_keeps_its_entry(self):
		unbranded = app_screen("frappe")
		self.assertEqual(unbranded["title"], "Framework")
		self.assertTrue(unbranded["logo"])
		self.assertIsNone(app_brand("frappe").get("favicon"))

	def test_a_brand_replaces_the_title_and_logo(self):
		with branded(BRAND):
			self.assertEqual(app_screen("frappe"), {"title": "Acme Sales", "logo": "/files/acme.png"})
			self.assertEqual(app_brand("frappe").get("favicon"), "/files/acme-icon.png")

	def test_a_brand_that_sets_only_a_favicon_keeps_the_title_and_logo(self):
		with branded(PARTIAL):
			self.assertEqual(app_screen("frappe"), app_screen("frappe", entry_without_brand()))
			self.assertEqual(app_brand("frappe").get("favicon"), "/files/acme-icon.png")

	def test_a_brand_that_raises_is_logged_and_the_entry_stands(self):
		with branded(RAISE), patch("frappe.log_error") as log_error:
			self.assertEqual(app_screen("frappe"), app_screen("frappe", entry_without_brand()))
			self.assertIsNone(app_brand("frappe").get("favicon"))

		log_error.assert_called_with(title="add_to_apps_screen brand failed for frappe")

	def test_a_brand_that_returns_no_dict_is_logged_and_the_entry_stands(self):
		with branded(LIST), patch("frappe.log_error") as log_error:
			self.assertEqual(app_screen("frappe"), app_screen("frappe", entry_without_brand()))

		log_error.assert_called_with(title="add_to_apps_screen brand failed for frappe")

	def test_only_string_values_of_a_brand_count(self):
		with branded(NON_STRING):
			self.assertEqual(app_screen("frappe")["title"], "Acme Sales")
			self.assertEqual(
				app_screen("frappe")["logo"], app_screen("frappe", entry_without_brand())["logo"]
			)
			self.assertIsNone(app_brand("frappe").get("favicon"))

	def test_the_app_boot_runs_the_brand_once(self):
		calls.clear()
		with branded(COUNTED):
			get_boot("/apps/desk")

		self.assertEqual(len(calls), 1)

	def test_index_tiles_carry_the_brand(self):
		with branded(BRAND):
			tile = next(tile for tile in index_tiles() if tile["app"] == "frappe")

		self.assertEqual((tile["title"], tile["logo"]), ("Acme Sales", "/files/acme.png"))
		self.assertNotIn("favicon", tile)

	def test_the_app_boot_carries_the_brand_and_the_index_boot_no_favicon(self):
		with branded(BRAND):
			boot = get_boot("/apps/desk")
			index = get_boot("/apps")

		self.assertEqual(
			(boot["app_title"], boot["app_logo"], boot["app_favicon"]),
			("Acme Sales", "/files/acme.png", "/files/acme-icon.png"),
		)
		self.assertNotIn("app_favicon", index)

	def test_the_app_boot_has_no_favicon_without_a_brand(self):
		self.assertIsNone(get_boot("/apps/desk")["app_favicon"])


def clear_request_cache():
	frappe.local.request_cache = defaultdict(dict)


def entry_without_brand() -> dict:
	entry = dict(frappe.get_hooks("add_to_apps_screen", app_name="frappe")[0])
	entry.pop("brand", None)
	return entry


@contextmanager
def branded(handler: str):
	"""Give frappe's `add_to_apps_screen` entry a `brand` of `handler`."""
	get_hooks = frappe.get_hooks

	def fake_hooks(hook=None, *args, **kwargs):
		hooks = get_hooks(hook, *args, **kwargs)
		if hook == "add_to_apps_screen" and kwargs.get("app_name") == "frappe":
			return [{**hooks[0], "brand": handler}]
		return hooks

	with patch("frappe.get_hooks", side_effect=fake_hooks):
		yield
