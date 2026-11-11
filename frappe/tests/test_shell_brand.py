# The `brand` of an app's `add_to_apps_screen` entry: site data over the entry's title and logo, and the app's tab icon.

import re
from collections import defaultdict
from contextlib import contextmanager
from unittest.mock import patch

import frappe
from frappe.shell.boot import get_boot, index_tiles
from frappe.shell.titles import DEFAULT_FAVICON, app_brand, app_screen, tab_icon
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.shell_page import get_shell_document
from frappe.website.serve import get_response

BRAND = "frappe.tests.test_shell_brand.brand"
PARTIAL = "frappe.tests.test_shell_brand.partial_brand"
RAISE = "frappe.tests.test_shell_brand.explode"
LIST = "frappe.tests.test_shell_brand.a_list"
BRAND_LOGO = "frappe.tests.test_shell_brand.logo_only_brand"
NON_STRING = "frappe.tests.test_shell_brand.non_string_logo"
COUNTED = "frappe.tests.test_shell_brand.counted_brand"


def brand():
	return {"title": "Acme Sales", "logo": "/files/acme.png", "favicon": "/files/acme-icon.png"}


def partial_brand():
	return {"favicon": "/files/acme-icon.png"}


def logo_only_brand():
	return {"logo": "/files/brand-logo.png"}


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

		self.assertEqual((boot["app_title"], boot["app_logo"]), ("Acme Sales", "/files/acme.png"))
		self.assertNotIn("app_favicon", boot)
		self.assertNotIn("app_favicon", index)


class TestTabIcon(IntegrationTestCase):
	"""The tab icon an app's prefix and the index get, in the owner's order of precedence."""

	def setUp(self):
		clear_request_cache()
		self.addCleanup(clear_request_cache)
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")

	def test_the_brand_favicon_comes_first(self):
		with (
			with_website_favicon("/files/site.png"),
			logo_entry("acme", "/files/acme-logo.png"),
			branded_app("acme", BRAND),
		):
			self.assertEqual(tab_icon("acme"), "/files/acme-icon.png")

	def test_the_tile_logo_comes_second(self):
		with with_website_favicon("/files/site.png"), logo_entry("acme", "/files/acme-logo.png"):
			self.assertEqual(tab_icon("acme"), "/files/acme-logo.png")

	def test_a_brand_logo_is_the_tile_logo(self):
		with logo_entry("acme", "/files/acme-logo.png"), branded_app("acme", BRAND_LOGO):
			self.assertEqual(tab_icon("acme"), "/files/brand-logo.png")

	def test_frappe_skips_its_own_logo(self):
		with with_website_favicon("/files/site.png"):
			self.assertEqual(tab_icon("frappe"), "/files/site.png")

		with with_website_favicon(None):
			self.assertEqual(tab_icon("frappe"), DEFAULT_FAVICON)

	def test_the_website_favicon_comes_third(self):
		with with_website_favicon("/files/site.png"), logo_entry("acme", None):
			self.assertEqual(tab_icon("acme"), "/files/site.png")

	def test_the_framework_icon_comes_last(self):
		for unset in (None, "", "attach_files:"):
			with self.subTest(favicon=unset), with_website_favicon(unset), logo_entry("acme", None):
				self.assertEqual(tab_icon("acme"), DEFAULT_FAVICON)

	def test_the_index_takes_the_website_favicon_then_the_framework_icon(self):
		with with_website_favicon("/files/site.png"):
			self.assertEqual(tab_icon(None), "/files/site.png")

		with with_website_favicon(None):
			self.assertEqual(tab_icon(None), DEFAULT_FAVICON)

	def test_a_logo_that_is_not_a_string_falls_through(self):
		with with_website_favicon("/files/site.png"), logo_entry("acme", {"url": "/files/acme.png"}):
			self.assertEqual(tab_icon("acme"), "/files/site.png")

	def test_a_brand_that_raises_falls_through(self):
		with (
			with_website_favicon("/files/site.png"),
			logo_entry("acme", "/files/acme-logo.png"),
			branded_app("acme", RAISE),
			patch("frappe.log_error"),
		):
			self.assertEqual(tab_icon("acme"), "/files/acme-logo.png")


class TestShellDocumentIcon(IntegrationTestCase):
	"""The icon is in the document the server sends, before any JS runs."""

	def setUp(self):
		clear_request_cache()
		self.addCleanup(clear_request_cache)
		frappe.set_user("Administrator")
		self.addCleanup(frappe.set_user, "Administrator")
		self.enterContext(self.change_settings("System Settings", enable_desk_v2=1))
		self.addCleanup(lambda: hasattr(frappe.local, "request") and delattr(frappe.local, "request"))

	def icon_of(self, path: str) -> str:
		set_request(method="GET", path=path)
		response = get_response()
		self.assertEqual(response.status_code, 200)
		match = re.search(rb'<link rel="icon" href="([^"]*)"', response.get_data())
		return match.group(1).decode()

	def test_each_prefix_gets_its_own_icon_from_the_one_memoized_document(self):
		with with_website_favicon("/files/site.png"), branded(BRAND):
			index = self.icon_of("/apps")
			desk = self.icon_of("/apps/desk")
			index_again = self.icon_of("/apps")

		self.assertEqual((index, desk, index_again), ("/files/site.png", "/files/acme-icon.png", index))

	def test_frappes_own_desk_falls_through_to_the_framework_icon(self):
		with with_website_favicon(None):
			self.assertEqual(self.icon_of("/apps/desk"), DEFAULT_FAVICON)

	def test_the_href_is_escaped_for_an_html_attribute(self):
		with with_website_favicon('/files/a.png?x="><script>&b=\\1'):
			icon = self.icon_of("/apps")

		self.assertEqual(icon, "/files/a.png?x=&quot;&gt;&lt;script&gt;&amp;b=\\1")

	def test_the_built_document_has_the_icon_link_the_server_replaces(self):
		self.assertRegex(get_shell_document(), r'<link rel="icon" href="[^"]*"')

	def test_a_brand_that_raises_still_renders_the_document(self):
		with with_website_favicon("/files/site.png"), branded(RAISE), patch("frappe.log_error"):
			self.assertEqual(self.icon_of("/apps/desk"), "/files/site.png")


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


@contextmanager
def with_website_favicon(favicon: str | None):
	with patch("frappe.get_website_settings", side_effect=lambda key: favicon if key == "favicon" else None):
		yield


@contextmanager
def logo_entry(app: str, logo: str | None):
	"""Give `app` an `add_to_apps_screen` entry with `logo`."""
	with entry_for(app, {"title": "Acme", "logo": logo}):
		yield


@contextmanager
def branded_app(app: str, handler: str):
	"""Give `app`'s `add_to_apps_screen` entry a `brand` of `handler`, keeping its other keys."""
	get_hooks = frappe.get_hooks

	def fake_hooks(hook=None, *args, **kwargs):
		hooks = get_hooks(hook, *args, **kwargs)
		if hook == "add_to_apps_screen" and kwargs.get("app_name") == app:
			return [{**(hooks[0] if hooks else {}), "brand": handler}]
		return hooks

	with patch("frappe.get_hooks", fake_hooks):
		yield


@contextmanager
def entry_for(app: str, entry: dict):
	get_hooks = frappe.get_hooks

	def fake_hooks(hook=None, *args, **kwargs):
		if hook == "add_to_apps_screen" and kwargs.get("app_name") == app:
			return [entry]
		return get_hooks(hook, *args, **kwargs)

	with patch("frappe.get_hooks", fake_hooks):
		yield
