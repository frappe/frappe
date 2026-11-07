import os
from unittest.mock import patch

import frappe
from frappe.studio import files
from frappe.studio.doctype.studio_app.test_studio_app import (
	exports_in_tempdir,
	make_studio_app,
	make_studio_page,
)
from frappe.studio.doctype.studio_app_file.studio_app_file import StudioAppFile
from frappe.tests import IntegrationTestCase

SETUP_SCRIPT = (
	'import { ref } from "vue"\nexport default function setup(context) {\n\treturn { count: ref(0) }\n}\n'
)


def write_export_file(folder, *parts, content="x"):
	path = os.path.join(folder, *parts)
	frappe.create_folder(os.path.dirname(path))
	with open(path, "w") as handle:
		handle.write(content)


def make_db_app(**kwargs):
	kwargs.setdefault("app_name", "db-app-" + frappe.generate_hash(length=8))
	kwargs.setdefault("app_title", kwargs["app_name"].title())
	return make_studio_app(**kwargs)


class TestFiles(IntegrationTestCase):
	def test_store_crud_and_tree(self):
		app = make_db_app()
		files.create_store_file(app.name, "utils/format.js")
		files.write_store_file(app.name, "utils/format.js", "export const one = 1\n")
		files.write_store_file(app.name, "components/card.css", ".card { color: red }\n")

		self.assertEqual(files.read_store_file(app.name, "utils/format.js"), "export const one = 1\n")
		self.assertIsNone(files.read_store_file(app.name, "missing.js"))

		tree = files.list_store_tree(app.name)
		self.assertEqual(
			[(node["path"], node["is_folder"]) for node in tree],
			[("components", True), ("utils", True)],
		)
		self.assertEqual(tree[1]["children"][0]["path"], "utils/format.js")

		paths = [file["path"] for file in files.get_store_files(app.name)]
		self.assertEqual(paths, ["components/card.css", "utils/format.js"])

	def test_a_page_script_is_browsed_and_edited_as_a_file(self):
		app = make_db_app()
		page = make_studio_page(app.name, page_title="Board")
		path = "studio_page/board/board.js"

		tree = files.list_store_tree(app.name)
		self.assertEqual([node["path"] for node in tree], ["studio_page"])
		self.assertEqual(tree[0]["children"][0]["children"][0]["path"], path)

		# Editing a page script updates its page record instead of creating a stored file.
		files.write_store_file(app.name, path, SETUP_SCRIPT)
		self.assertEqual(frappe.db.get_value("Studio Page", page.name, "script"), SETUP_SCRIPT)
		self.assertEqual(files.read_store_file(app.name, path), SETUP_SCRIPT)
		self.assertEqual(files.get_store_files(app.name), [])

		with self.assertRaises(frappe.ValidationError):
			files.rename_store_path(app.name, path, "studio_page/board/renamed.js")
		files.delete_store_path(app.name, path)
		self.assertEqual(files.read_store_file(app.name, path), "")

	def test_path_rules(self):
		app = make_db_app()
		# Reject paths that could escape the app root, as the disk explorer does.
		for traversal in ("../escape.js", "a//b.js", "./x.js"):
			with self.assertRaises(frappe.PermissionError, msg=traversal):
				files.create_store_file(app.name, traversal)
		for bad_path in (
			"run.py",
			"tailwind.config.js",
			f"{frappe.scrub(app.name)}.json",
			"studio_page/home/home.json",
			"studio_components/card.json",
		):
			with self.assertRaises(frappe.ValidationError, msg=bad_path):
				files.create_store_file(app.name, bad_path)

	def test_duplicate_and_conflict_checks(self):
		app = make_db_app()
		files.create_store_file(app.name, "a.js")
		with self.assertRaises(frappe.ValidationError):
			files.create_store_file(app.name, "a.js")

		files.write_store_file(app.name, "a.js", "let x = 1\n")
		stale_hash = files.file_hash("something else")
		with self.assertRaises(frappe.ValidationError):
			files.write_store_file(app.name, "a.js", "let x = 2\n", known_hash=stale_hash)
		files.write_store_file(app.name, "a.js", "let x = 2\n", known_hash=files.file_hash("let x = 1\n"))
		self.assertEqual(files.read_store_file(app.name, "a.js"), "let x = 2\n")

		# A folder name with a source extension would put a file inside another file.
		for bad_path in ("a.js/format.js", "lib/helpers.ts/format.js"):
			with self.assertRaises(frappe.ValidationError, msg=bad_path) as refused:
				files.write_store_file(app.name, bad_path, "let y = 1\n")
			self.assertIn("is a folder", str(refused.exception))

	def test_the_file_path_index_catches_a_duplicate_the_app_check_misses(self):
		app = make_db_app()
		files.create_store_file(app.name, "a.js")

		frappe.db.savepoint("duplicate_path")
		with patch.object(StudioAppFile, "validate_unique_path"):
			with self.assertRaises(frappe.UniqueValidationError):
				files.insert_store_row(app.name, "a.js", "")
		frappe.db.rollback(save_point="duplicate_path")

	def test_rename_and_delete_folders_move_subtrees(self):
		app = make_db_app()
		files.write_store_file(app.name, "utils/a.js", "export const a = 1\n")
		files.write_store_file(app.name, "utils/deep/b.js", "export const b = 2\n")

		files.rename_store_path(app.name, "utils", "lib")
		self.assertEqual(
			[file["path"] for file in files.get_store_files(app.name)], ["lib/a.js", "lib/deep/b.js"]
		)
		with self.assertRaises(frappe.ValidationError):
			files.rename_store_path(app.name, "missing.js", "found.js")

		files.delete_store_path(app.name, "lib/deep")
		self.assertEqual([file["path"] for file in files.get_store_files(app.name)], ["lib/a.js"])

	def test_is_db_app(self):
		with exports_in_tempdir():
			db_app = make_db_app()
			repo_app = make_db_app(is_standard=1, frappe_app="frappe")
		self.assertTrue(files.is_db_app(db_app.name))
		self.assertFalse(files.is_db_app(repo_app.name))
		# A missing app does not use database file storage.
		self.assertFalse(files.is_db_app("no-such-app"))

	def test_an_app_that_was_never_exported_discards_nothing(self):
		self.assertEqual(files.discarded_export_files(make_db_app()), [])

	def test_export_round_trip(self):
		with exports_in_tempdir():
			app = make_db_app()
			page = make_studio_page(app.name, page_title="Board", script=SETUP_SCRIPT)
			files.write_store_file(app.name, "components/card.css", ".card { color: red }\n")
			files.write_store_file(app.name, "router.js", "export default {}\n")

			app.reload()
			app.enable_app_export("frappe")

			folder = app.get_folder_path()
			self.assertEqual(
				frappe.read_file(os.path.join(folder, "components", "card.css")),
				".card { color: red }\n",
			)
			self.assertEqual(frappe.read_file(os.path.join(folder, "router.js")), "export default {}\n")
			# Export preserves the script's content in its companion .js file.
			self.assertEqual(
				frappe.read_file(os.path.join(folder, "studio_page", "board", "board.js")), SETUP_SCRIPT
			)
			# After export, source files belong to the repository and the store is empty.
			self.assertEqual(files.get_store_files(app.name), [])

			app.reload()
			app.disable_app_export()

			self.assertEqual(files.read_store_file(app.name, "components/card.css"), ".card { color: red }\n")
			self.assertEqual(files.read_store_file(app.name, "router.js"), "export default {}\n")
			self.assertEqual(frappe.db.get_value("Studio Page", page.name, "script"), SETUP_SCRIPT)

	def test_disabling_export_refuses_to_delete_files_the_store_cannot_hold(self):
		with exports_in_tempdir():
			app = make_db_app()
			make_studio_page(app.name, page_title="Board", script=SETUP_SCRIPT)
			files.write_store_file(app.name, "components/card.css", ".card { color: red }\n")

			app.reload()
			app.enable_app_export("frappe")

			folder = app.get_folder_path()
			# A repository can contain files that the database store does not support.
			write_export_file(folder, "assets", "icon.svg", content="<svg />")
			write_export_file(folder, "components", "Card.vue")
			write_export_file(folder, "stores", "catalog.ts")
			write_export_file(folder, "studio_page", "board", "Card.vue")
			write_export_file(folder, "tailwind.config.js")

			app.reload()
			with self.assertRaises(frappe.ValidationError) as refused:
				app.disable_app_export()
			for path in (
				"assets/icon.svg",
				"components/Card.vue",
				"stores/catalog.ts",
				"studio_page/board/Card.vue",
				"tailwind.config.js",
			):
				self.assertIn(path, str(refused.exception))
			# Rejecting the operation preserves the existing export.
			self.assertTrue(os.path.isdir(folder))
			self.assertEqual(frappe.db.get_value("Studio App", app.name, "is_standard"), 1)

			app.reload()
			app.disable_app_export(confirm_discarded=True)
			self.assertEqual(files.read_store_file(app.name, "components/card.css"), ".card { color: red }\n")
			self.assertIsNone(files.read_store_file(app.name, "components/Card.vue"))
			self.assertEqual(
				frappe.db.get_value("Studio Page", {"studio_app": app.name}, "script"), SETUP_SCRIPT
			)

	def test_deleting_app_deletes_store(self):
		app = make_db_app()
		files.write_store_file(app.name, "a.js", "let x = 1\n")
		app.delete()
		self.assertEqual(frappe.db.count("Studio App File", {"studio_app": app.name}), 0)
