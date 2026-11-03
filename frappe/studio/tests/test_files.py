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
		files.create_store_file(app.name, "utils/format.ts")
		files.write_store_file(app.name, "utils/format.ts", "export const one = 1\n")
		files.write_store_file(app.name, "components/Card.vue", "<template><div /></template>\n")
		files.create_store_folder(app.name, "assets")

		self.assertEqual(files.read_store_file(app.name, "utils/format.ts"), "export const one = 1\n")
		self.assertIsNone(files.read_store_file(app.name, "missing.ts"))

		tree = files.list_store_tree(app.name)
		self.assertEqual(
			[(node["path"], node["is_folder"]) for node in tree],
			[("assets", True), ("components", True), ("utils", True)],
		)
		self.assertEqual(tree[2]["children"][0]["path"], "utils/format.ts")

		paths = [file["path"] for file in files.get_store_files(app.name)]
		self.assertEqual(paths, ["components/Card.vue", "utils/format.ts"])

	def test_path_rules(self):
		app = make_db_app()
		# path tricks are a jail escape, like the disk explorer treats them
		for traversal in ("../escape.ts", "a//b.ts", "./x.ts"):
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
		with self.assertRaises(frappe.ValidationError):
			files.create_store_folder(app.name, "studio_page")

	def test_duplicate_and_conflict_checks(self):
		app = make_db_app()
		files.create_store_file(app.name, "a.ts")
		with self.assertRaises(frappe.ValidationError):
			files.create_store_file(app.name, "a.ts")

		files.write_store_file(app.name, "a.ts", "let x = 1\n")
		stale_hash = files.file_hash("something else")
		with self.assertRaises(frappe.ValidationError):
			files.write_store_file(app.name, "a.ts", "let x = 2\n", known_hash=stale_hash)
		files.write_store_file(app.name, "a.ts", "let x = 2\n", known_hash=files.file_hash("let x = 1\n"))
		self.assertEqual(files.read_store_file(app.name, "a.ts"), "let x = 2\n")

	def test_the_file_path_index_catches_a_duplicate_the_app_check_misses(self):
		app = make_db_app()
		files.create_store_file(app.name, "a.ts")

		frappe.db.savepoint("duplicate_path")
		with patch.object(StudioAppFile, "validate_unique_path"):
			with self.assertRaises(frappe.UniqueValidationError):
				files.insert_store_row(app.name, "a.ts", "")
		frappe.db.rollback(save_point="duplicate_path")

	def test_rename_and_delete_folders_move_subtrees(self):
		app = make_db_app()
		files.write_store_file(app.name, "utils/a.ts", "export const a = 1\n")
		files.write_store_file(app.name, "utils/deep/b.ts", "export const b = 2\n")

		files.rename_store_path(app.name, "utils", "lib")
		self.assertEqual(
			[file["path"] for file in files.get_store_files(app.name)], ["lib/a.ts", "lib/deep/b.ts"]
		)
		with self.assertRaises(frappe.ValidationError):
			files.rename_store_path(app.name, "missing.ts", "found.ts")

		files.delete_store_path(app.name, "lib/deep")
		self.assertEqual([file["path"] for file in files.get_store_files(app.name)], ["lib/a.ts"])

	def test_uses_db_files(self):
		with exports_in_tempdir():
			db_app = make_db_app()
			repo_app = make_db_app(is_standard=1, frappe_app="frappe")
		self.assertTrue(files.uses_db_files(db_app.name))
		self.assertFalse(files.uses_db_files(repo_app.name))
		# a missing app falls through to the disk jail, which rejects it
		self.assertFalse(files.uses_db_files("no-such-app"))

	def test_export_round_trip(self):
		with exports_in_tempdir():
			app = make_db_app()
			page = make_studio_page(app.name, page_title="Board", script=SETUP_SCRIPT)
			files.write_store_file(app.name, "components/Card.vue", "<template><b>hi</b></template>\n")
			files.write_store_file(app.name, "router.ts", "export default {}\n")
			files.create_store_folder(app.name, "assets")

			app.reload()
			app.enable_app_export("frappe")

			folder = app.get_folder_path()
			self.assertEqual(
				frappe.read_file(os.path.join(folder, "components", "Card.vue")),
				"<template><b>hi</b></template>\n",
			)
			self.assertEqual(frappe.read_file(os.path.join(folder, "router.ts")), "export default {}\n")
			self.assertTrue(os.path.isdir(os.path.join(folder, "assets")))
			# the page script moved to its companion .ts verbatim
			self.assertEqual(
				frappe.read_file(os.path.join(folder, "studio_page", "board", "board.ts")), SETUP_SCRIPT
			)
			# the store emptied: the repository owns the files now
			self.assertEqual(files.get_store_files(app.name), [])

			app.reload()
			app.disable_app_export()

			self.assertEqual(
				files.read_store_file(app.name, "components/Card.vue"), "<template><b>hi</b></template>\n"
			)
			self.assertEqual(files.read_store_file(app.name, "router.ts"), "export default {}\n")
			self.assertEqual(frappe.db.get_value("Studio Page", page.name, "script"), SETUP_SCRIPT)

	def test_disabling_export_refuses_to_delete_files_the_store_cannot_hold(self):
		with exports_in_tempdir():
			app = make_db_app()
			make_studio_page(app.name, page_title="Board", script=SETUP_SCRIPT)
			files.write_store_file(app.name, "components/Card.vue", "<template><b>hi</b></template>\n")

			app.reload()
			app.enable_app_export("frappe")

			folder = app.get_folder_path()
			# a repository app collects files the store has no home for
			write_export_file(folder, "assets", "icon.svg", content="<svg />")
			write_export_file(folder, "studio_page", "board", "Card.vue")
			write_export_file(folder, "tailwind.config.js")

			app.reload()
			with self.assertRaises(frappe.ValidationError) as refused:
				app.disable_app_export()
			for path in ("assets/icon.svg", "studio_page/board/Card.vue", "tailwind.config.js"):
				self.assertIn(path, str(refused.exception))
			# the refusal changed nothing
			self.assertTrue(os.path.isdir(folder))
			self.assertEqual(frappe.db.get_value("Studio App", app.name, "is_standard"), 1)

			app.reload()
			app.disable_app_export(confirm_discarded=True)
			self.assertEqual(
				files.read_store_file(app.name, "components/Card.vue"), "<template><b>hi</b></template>\n"
			)
			self.assertEqual(
				frappe.db.get_value("Studio Page", {"studio_app": app.name}, "script"), SETUP_SCRIPT
			)

	def test_deleting_app_deletes_store(self):
		app = make_db_app()
		files.write_store_file(app.name, "a.ts", "let x = 1\n")
		app.delete()
		self.assertEqual(frappe.db.count("Studio App File", {"studio_app": app.name}), 0)
