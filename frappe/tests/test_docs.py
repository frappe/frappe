import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.desk.docs import (
	build_navigation_tree,
	discover_pages,
	get_first_page,
	get_locales,
	get_page,
	get_page_record,
	get_page_variants,
	get_tree,
	merge_translated_page,
	normalize_path,
	parse_roles,
	render_page_content,
	resolve_asset_path,
	resolve_locale,
)
from frappe.tests import IntegrationTestCase


class TestDocs(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.local.lang = "en"

	def test_discover_hierarchy_and_index_paths(self):
		with self.docs_environment(
			{
				"en/index.md": "---\ntitle: Home\n---\n# Home",
				"en/guides/index.md": "---\ntitle: Guides\n---\n# Guides",
				"en/guides/setup.md": "---\ntitle: Setup\norder: 2\n---\n# Setup",
			}
		) as docs_root:
			pages = discover_pages("en")
			self.assertEqual(pages[""].title, "Home")
			self.assertEqual(pages["guides"].title, "Guides")
			self.assertEqual(pages["guides/setup"].title, "Setup")
			self.assertTrue(os.path.commonpath([pages["guides/setup"].filepath, docs_root]) == docs_root)

	def test_frontmatter_defaults_and_role_parsing(self):
		self.assertEqual(parse_roles(None), ["Desk User"])
		self.assertEqual(parse_roles("System Manager, Desk User"), ["System Manager", "Desk User"])
		self.assertEqual(parse_roles(["Desk User"]), ["Desk User"])

		with self.docs_environment({"en/restricted.md": "# Restricted"}):
			page = discover_pages("en")["restricted"]
			self.assertEqual(page.roles, ["Desk User"])

	def test_later_app_wins_on_same_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			first_app = os.path.join(tmp, "first_app")
			second_app = os.path.join(tmp, "second_app")
			for app_root in (first_app, second_app):
				os.makedirs(os.path.join(app_root, "docs", "en"))

			with open(os.path.join(first_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: First\n---\nFirst body")
			with open(os.path.join(second_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: Second\n---\nSecond body")

			with patch(
				"frappe.desk.docs.frappe.get_installed_apps", return_value=["first_app", "second_app"]
			):

				def get_app_path(app):
					return os.path.join(tmp, app)

				with patch("frappe.desk.docs.frappe.get_app_path", side_effect=get_app_path):
					page = discover_pages("en")["shared"]
					self.assertEqual(page.app, "second_app")
					self.assertEqual(page.title, "Second")

	def test_role_filtering_and_permission_error(self):
		with self.docs_environment(
			{
				"en/public.md": "---\ntitle: Public\nroles: Desk User\n---\n# Public",
				"en/admin.md": "---\ntitle: Admin\nroles: System Manager\n---\n# Admin",
			}
		):
			frappe.set_user("Administrator")
			tree = build_navigation_tree("en")
			paths = {node["path"] for node in tree}
			self.assertIn("public", paths)
			self.assertIn("admin", paths)

			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				tree = build_navigation_tree("en")
				paths = {node["path"] for node in tree}
				self.assertIn("public", paths)
				self.assertNotIn("admin", paths)

				get_page("public", locale="en")
				with self.assertRaises(frappe.PermissionError):
					get_page("admin", locale="en")

	def test_direct_access_denied_raises_permission_error(self):
		with self.docs_environment({"en/admin.md": "---\ntitle: Admin\nroles: System Manager\n---\n# Admin"}):
			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				with self.assertRaises(frappe.PermissionError):
					get_page_record("admin", check_permission=True)

	def test_path_traversal_is_rejected(self):
		with self.assertRaises(frappe.ValidationError):
			normalize_path("../secrets")
		with self.assertRaises(frappe.ValidationError):
			normalize_path("foo/../../etc/passwd")

	def test_sanitized_markdown_and_asset_rewrite(self):
		with self.docs_environment(
			{
				"en/page.md": "---\ntitle: Page\n---\n![Logo](./logo.png)\n\n<script>alert(1)</script>",
				"en/logo.png": "binary",
			}
		):
			page = discover_pages("en")["page"]
			html = render_page_content(page.body, page.path, "en")
			self.assertIn("get_asset", html)
			self.assertNotIn("<script>", html)

	def test_protected_assets_require_page_access(self):
		with self.docs_environment(
			{
				"en/assets.md": "---\ntitle: Assets\nroles: System Manager\n---\n# Assets",
				"en/logo.png": "logo-bytes",
			}
		):
			page = discover_pages("en")["assets"]
			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				with self.assertRaises(frappe.PermissionError):
					get_page_record("assets", locale="en", check_permission=True)

			frappe.set_user("Administrator")
			asset_file = resolve_asset_path(page, "logo.png")
			self.assertTrue(asset_file.endswith("logo.png"))

	def test_get_first_page_and_tree_ordering(self):
		with self.docs_environment(
			{
				"en/b.md": "---\ntitle: B\norder: 2\n---\n# B",
				"en/a.md": "---\ntitle: A\norder: 1\n---\n# A",
			}
		):
			self.assertEqual(get_first_page("en"), "a")
			tree = get_tree("en")
			self.assertEqual([node["title"] for node in tree], ["A", "B"])

	def test_get_first_page_returns_root_path(self):
		with self.docs_environment({"en/index.md": "---\ntitle: Home\norder: 0\n---\n# Home"}):
			self.assertEqual(get_first_page("en"), "")

	def test_framework_example_docs_exist(self):
		docs_root = os.path.join(frappe.get_app_path("frappe"), "docs")
		self.assertTrue(os.path.isdir(docs_root))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "en", "framework", "index.md")))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "en", "framework", "docs", "index.md")))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "en", "framework", "docs", "authoring.md")))

	def test_navigation_tree_includes_folder_nodes(self):
		with self.docs_environment({"en/folder/leaf.md": "---\ntitle: Leaf\n---\n# Leaf"}):
			tree = build_navigation_tree("en")
			folder = next(node for node in tree if node["path"] == "folder")
			self.assertFalse(folder["has_page"])
			self.assertEqual(folder["children"][0]["path"], "folder/leaf")

	def test_localized_translation_overrides_english_content(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\norder: 1\nroles: Desk User\n---\n# English",
				"de/guide.md": "---\ntitle: Leitfaden\n---\n# Deutsch",
			}
		):
			page = discover_pages("de")["guide"]
			self.assertEqual(page.title, "Leitfaden")
			self.assertIn("Deutsch", page.body)
			self.assertEqual(page.order, 1)
			self.assertEqual(page.roles, ["Desk User"])

	def test_parent_language_fallback(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\n---\n# English",
				"de/guide.md": "---\ntitle: Leitfaden\n---\n# Deutsch",
			}
		):
			page = discover_pages("de-CH")["guide"]
			self.assertEqual(page.title, "Leitfaden")

	def test_missing_translation_falls_back_to_english(self):
		with self.docs_environment({"en/guide.md": "---\ntitle: Guide\n---\n# English"}):
			page = discover_pages("de")["guide"]
			self.assertEqual(page.title, "Guide")
			self.assertIn("English", page.body)

	def test_localized_only_path_visible_for_matching_language(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\n---\n# English",
				"de/country/tax.md": "---\ntitle: Steuer\norder: 5\nroles: Desk User\n---\n# Steuer",
			}
		):
			pages = discover_pages("de")
			self.assertIn("country/tax", pages)
			self.assertEqual(pages["country/tax"].title, "Steuer")
			self.assertEqual(pages["country/tax"].order, 5)

			pages = discover_pages("en")
			self.assertNotIn("country/tax", pages)

	def test_localized_only_path_renders_for_other_language_user(self):
		with self.docs_environment(
			{
				"de/country/tax.md": "---\ntitle: Steuer\nroles: Desk User\n---\n# Steuer",
			}
		):
			self.assertNotIn("country/tax", discover_pages("en"))

			page = get_page_record("country/tax", locale="de")
			self.assertEqual(page.title, "Steuer")
			self.assertIn("Steuer", get_page("country/tax", locale="de")["content"])

			page = get_page_record("country/tax", locale="en")
			self.assertEqual(page.title, "Steuer")
			self.assertIn("Steuer", get_page("country/tax", locale="en")["content"])

	def test_localized_only_path_uses_own_roles(self):
		with self.docs_environment(
			{
				"de/secret.md": "---\ntitle: Geheim\nroles: System Manager\n---\n# Geheim",
			}
		):
			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				with self.assertRaises(frappe.PermissionError):
					get_page_record("secret", locale="de", check_permission=True)

	def test_older_translation_does_not_override_newer_english(self):
		with tempfile.TemporaryDirectory() as tmp:
			first_app = os.path.join(tmp, "first_app")
			second_app = os.path.join(tmp, "second_app")
			for app_root in (first_app, second_app):
				os.makedirs(os.path.join(app_root, "docs", "en"))
				os.makedirs(os.path.join(app_root, "docs", "de"))

			with open(os.path.join(first_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: English First\n---\nEnglish first")
			with open(os.path.join(first_app, "docs", "de", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: Deutsch Alt\n---\nDeutsch alt")
			with open(os.path.join(second_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: English Second\n---\nEnglish second")

			with patch(
				"frappe.desk.docs.frappe.get_installed_apps", return_value=["first_app", "second_app"]
			):

				def get_app_path(app):
					return os.path.join(tmp, app)

				with patch("frappe.desk.docs.frappe.get_app_path", side_effect=get_app_path):
					page = discover_pages("de")["shared"]
					self.assertEqual(page.title, "English Second")
					self.assertIn("English second", page.body)

	def test_translation_from_later_app_applies(self):
		with tempfile.TemporaryDirectory() as tmp:
			first_app = os.path.join(tmp, "first_app")
			second_app = os.path.join(tmp, "second_app")
			for app_root in (first_app, second_app):
				os.makedirs(os.path.join(app_root, "docs", "en"))
				os.makedirs(os.path.join(app_root, "docs", "de"))

			with open(os.path.join(first_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: English First\n---\nEnglish first")
			with open(os.path.join(second_app, "docs", "en", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: English Second\n---\nEnglish second")
			with open(os.path.join(second_app, "docs", "de", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: Deutsch Neu\n---\nDeutsch neu")

			with patch(
				"frappe.desk.docs.frappe.get_installed_apps", return_value=["first_app", "second_app"]
			):

				def get_app_path(app):
					return os.path.join(tmp, app)

				with patch("frappe.desk.docs.frappe.get_app_path", side_effect=get_app_path):
					page = discover_pages("de")["shared"]
					self.assertEqual(page.title, "Deutsch Neu")
					self.assertIn("Deutsch neu", page.body)

	def test_merge_translated_page_inherits_canonical_metadata(self):
		canonical = frappe._dict(
			{"path": "guide", "title": "Guide", "order": 3, "roles": ["Desk User"], "body": "English"}
		)
		localized = frappe._dict(
			{
				"path": "guide",
				"title": "Leitfaden",
				"order": 9,
				"roles": ["System Manager"],
				"body": "Deutsch",
				"app": "frappe",
				"app_index": 0,
				"language": "de",
				"filepath": "/tmp/de.md",
				"basepath": "/tmp",
				"docs_root": "/tmp/docs",
				"app_path": "/tmp",
			}
		)
		merged = merge_translated_page(canonical, localized)
		self.assertEqual(merged.title, "Leitfaden")
		self.assertEqual(merged.body, "Deutsch")
		self.assertEqual(merged.order, 3)
		self.assertEqual(merged.roles, ["Desk User"])

	def test_compose_pages_with_localized_assets(self):
		with self.docs_environment(
			{
				"en/page.md": "---\ntitle: Page\n---\n![Logo](./logo.png)",
				"de/page.md": "---\ntitle: Seite\n---\n![Logo](./de-logo.png)",
				"en/logo.png": "english-logo",
				"de/de-logo.png": "german-logo",
			}
		):
			page = discover_pages("de")["page"]
			asset_file = resolve_asset_path(page, "de-logo.png")
			self.assertTrue(asset_file.endswith("de-logo.png"))

	def test_files_without_language_prefix_are_ignored(self):
		with self.docs_environment({"guide.md": "---\ntitle: Guide\n---\n# Guide"}):
			pages = discover_pages("en")
			self.assertNotIn("guide", pages)

	def test_resolve_locale_uses_user_language_when_translation_exists(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\n---\n# English",
				"de/guide.md": "---\ntitle: Leitfaden\n---\n# Deutsch",
			}
		):
			frappe.local.lang = "de"
			self.assertEqual(resolve_locale("guide"), {"locale": "de", "path": "guide"})

	def test_resolve_locale_falls_back_to_english_without_translation(self):
		with self.docs_environment({"en/guide.md": "---\ntitle: Guide\n---\n# English"}):
			frappe.local.lang = "de"
			self.assertEqual(resolve_locale("guide"), {"locale": "en", "path": "guide"})

	def test_resolve_locale_uses_user_language_for_localized_only_path(self):
		with self.docs_environment({"de/country/tax.md": "---\ntitle: Steuer\n---\n# Steuer"}):
			frappe.local.lang = "de"
			self.assertEqual(resolve_locale("country/tax"), {"locale": "de", "path": "country/tax"})

	def test_resolve_locale_uses_content_locale_for_localized_only_path(self):
		with self.docs_environment({"fr/country/tax.md": "---\ntitle: Taxe\n---\n# Taxe"}):
			frappe.local.lang = "en"
			self.assertEqual(resolve_locale("country/tax"), {"locale": "fr", "path": "country/tax"})

	def test_get_locales_returns_documented_locales_with_labels(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\n---\n# English",
				"de/guide.md": "---\ntitle: Leitfaden\n---\n# Deutsch",
			}
		):
			locales = {item["locale"] for item in get_locales()}
			self.assertEqual(locales, {"de", "en"})
			labels = {item["locale"]: item["label"] for item in get_locales()}
			self.assertTrue(labels["en"])
			self.assertTrue(labels["de"])

	def test_get_page_variants_lists_accessible_locales_for_path(self):
		with self.docs_environment(
			{
				"en/guide.md": "---\ntitle: Guide\n---\n# English",
				"de/guide.md": "---\ntitle: Leitfaden\n---\n# Deutsch",
				"de/country/tax.md": "---\ntitle: Steuer\n---\n# Steuer",
			}
		):
			variants = get_page_variants("guide")
			self.assertEqual([variant["locale"] for variant in variants], ["de", "en"])
			self.assertEqual(variants[0]["title"], "Leitfaden")

			localized_only = get_page_variants("country/tax")
			self.assertEqual([variant["locale"] for variant in localized_only], ["de"])

	def docs_environment(self, files):
		return DocsTestEnvironment(files)


class DocsTestEnvironment:
	def __init__(self, files):
		self.files = files
		self.tmpdir = None
		self.docs_root = None
		self._patches = []

	def __enter__(self):
		self.tmpdir = tempfile.TemporaryDirectory()
		app_root = os.path.join(self.tmpdir.name, "frappe")
		self.docs_root = os.path.join(app_root, "docs")
		os.makedirs(self.docs_root, exist_ok=True)

		for relative_path, content in self.files.items():
			filepath = os.path.join(self.docs_root, relative_path)
			os.makedirs(os.path.dirname(filepath), exist_ok=True)
			mode = "wb" if isinstance(content, bytes) else "w"
			encoding = None if isinstance(content, bytes) else "utf-8"
			with open(filepath, mode, encoding=encoding) as f:
				f.write(content)

		self._patches = [
			patch("frappe.desk.docs.frappe.get_installed_apps", return_value=["frappe"]),
			patch("frappe.desk.docs.frappe.get_app_path", return_value=app_root),
		]
		for patcher in self._patches:
			patcher.start()
		return self.docs_root

	def __exit__(self, exc_type, exc, tb):
		for patcher in reversed(self._patches):
			patcher.stop()
		self.tmpdir.cleanup()
