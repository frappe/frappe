import os
import tempfile
from unittest.mock import patch

import frappe
from frappe.desk.docs import (
	build_navigation_tree,
	discover_pages,
	get_first_page,
	get_page,
	get_page_record,
	get_tree,
	normalize_path,
	parse_roles,
	render_page_content,
	resolve_asset_path,
)
from frappe.tests import IntegrationTestCase


class TestDocs(IntegrationTestCase):
	def setUp(self):
		frappe.set_user("Administrator")

	def tearDown(self):
		frappe.set_user("Administrator")

	def test_discover_hierarchy_and_index_paths(self):
		with self.docs_environment(
			{
				"index.md": "---\ntitle: Home\n---\n# Home",
				"guides/index.md": "---\ntitle: Guides\n---\n# Guides",
				"guides/setup.md": "---\ntitle: Setup\norder: 2\n---\n# Setup",
			}
		) as docs_root:
			pages = discover_pages()
			self.assertEqual(pages[""].title, "Home")
			self.assertEqual(pages["guides"].title, "Guides")
			self.assertEqual(pages["guides/setup"].title, "Setup")
			self.assertTrue(os.path.commonpath([pages["guides/setup"].filepath, docs_root]) == docs_root)

	def test_frontmatter_defaults_and_role_parsing(self):
		self.assertEqual(parse_roles(None), ["Desk User"])
		self.assertEqual(parse_roles("System Manager, Desk User"), ["System Manager", "Desk User"])
		self.assertEqual(parse_roles(["Desk User"]), ["Desk User"])

		with self.docs_environment({"restricted.md": "# Restricted"}):
			page = discover_pages()["restricted"]
			self.assertEqual(page.roles, ["Desk User"])

	def test_later_app_wins_on_same_path(self):
		with tempfile.TemporaryDirectory() as tmp:
			first_app = os.path.join(tmp, "first_app")
			second_app = os.path.join(tmp, "second_app")
			for app_root in (first_app, second_app):
				os.makedirs(os.path.join(app_root, "docs"))

			with open(os.path.join(first_app, "docs", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: First\n---\nFirst body")
			with open(os.path.join(second_app, "docs", "shared.md"), "w", encoding="utf-8") as f:
				f.write("---\ntitle: Second\n---\nSecond body")

			with patch(
				"frappe.desk.docs.frappe.get_installed_apps", return_value=["first_app", "second_app"]
			):

				def get_app_path(app):
					return os.path.join(tmp, app)

				with patch("frappe.desk.docs.frappe.get_app_path", side_effect=get_app_path):
					page = discover_pages()["shared"]
					self.assertEqual(page.app, "second_app")
					self.assertEqual(page.title, "Second")

	def test_role_filtering_and_permission_error(self):
		with self.docs_environment(
			{
				"public.md": "---\ntitle: Public\nroles: Desk User\n---\n# Public",
				"admin.md": "---\ntitle: Admin\nroles: System Manager\n---\n# Admin",
			}
		):
			frappe.set_user("Administrator")
			tree = build_navigation_tree()
			paths = {node["path"] for node in tree}
			self.assertIn("public", paths)
			self.assertIn("admin", paths)

			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				tree = build_navigation_tree()
				paths = {node["path"] for node in tree}
				self.assertIn("public", paths)
				self.assertNotIn("admin", paths)

				get_page("public")
				with self.assertRaises(frappe.PermissionError):
					get_page("admin")

	def test_direct_access_denied_raises_permission_error(self):
		with self.docs_environment({"admin.md": "---\ntitle: Admin\nroles: System Manager\n---\n# Admin"}):
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
				"page.md": "---\ntitle: Page\n---\n![Logo](./logo.png)\n\n<script>alert(1)</script>",
				"logo.png": "binary",
			}
		):
			page = discover_pages()["page"]
			html = render_page_content(page.body, page.path)
			self.assertIn("get_asset", html)
			self.assertNotIn("<script>", html)

	def test_protected_assets_require_page_access(self):
		with self.docs_environment(
			{
				"assets.md": "---\ntitle: Assets\nroles: System Manager\n---\n# Assets",
				"logo.png": "logo-bytes",
			}
		):
			page = discover_pages()["assets"]
			frappe.set_user("test@example.com")
			with patch("frappe.desk.docs.frappe.get_roles", return_value=["Desk User"]):
				with self.assertRaises(frappe.PermissionError):
					get_page_record("assets", check_permission=True)

			frappe.set_user("Administrator")
			asset_file = resolve_asset_path(page, "logo.png")
			self.assertTrue(asset_file.endswith("logo.png"))

	def test_get_first_page_and_tree_ordering(self):
		with self.docs_environment(
			{
				"b.md": "---\ntitle: B\norder: 2\n---\n# B",
				"a.md": "---\ntitle: A\norder: 1\n---\n# A",
			}
		):
			self.assertEqual(get_first_page(), "a")
			tree = get_tree()
			self.assertEqual([node["title"] for node in tree], ["A", "B"])

	def test_get_first_page_returns_root_path(self):
		with self.docs_environment({"index.md": "---\ntitle: Home\norder: 0\n---\n# Home"}):
			self.assertEqual(get_first_page(), "")

	def test_framework_example_docs_exist(self):
		docs_root = os.path.join(frappe.get_app_path("frappe"), "docs")
		self.assertTrue(os.path.isdir(docs_root))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "framework", "index.md")))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "framework", "docs", "index.md")))
		self.assertTrue(os.path.isfile(os.path.join(docs_root, "framework", "docs", "authoring.md")))

	def test_navigation_tree_includes_folder_nodes(self):
		with self.docs_environment({"folder/leaf.md": "---\ntitle: Leaf\n---\n# Leaf"}):
			tree = build_navigation_tree()
			folder = next(node for node in tree if node["path"] == "folder")
			self.assertFalse(folder["has_page"])
			self.assertEqual(folder["children"][0]["path"], "folder/leaf")

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
