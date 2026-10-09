# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json
import os
import tempfile

import frappe
from frappe.core.doctype.migration_hash.migration_hash import get_migration_hash, get_relative_file_path
from frappe.modules.import_file import calculate_hash, import_file_by_path
from frappe.tests import IntegrationTestCase

MODIFIED = "2020-01-01 00:00:00.000000"


def write_note_file(folder: str, name: str, content: str) -> str:
	"""Write a Note as a synced JSON file, always with the same `modified`."""
	path = os.path.join(folder, "note.json")
	with open(path, "w") as f:
		json.dump(
			{"doctype": "Note", "name": name, "title": name, "content": content, "modified": MODIFIED}, f
		)
	return path


class IntegrationTestMigrationHash(IntegrationTestCase):
	def test_file_changed_without_new_modified_is_imported(self):
		name = "_Test Migration Hash Changed"
		with tempfile.TemporaryDirectory() as folder:
			path = write_note_file(folder, name, "first")
			self.assertTrue(import_file_by_path(path))

			write_note_file(folder, name, "second")
			self.assertTrue(import_file_by_path(path))
			self.assertEqual(frappe.db.get_value("Note", name, "content"), "second")
			self.assertEqual(get_migration_hash(path), calculate_hash(path))

			self.assertFalse(import_file_by_path(path))

	def test_stale_record_without_hash_is_imported_once(self):
		name = "_Test Migration Hash Stale"
		with tempfile.TemporaryDirectory() as folder:
			path = write_note_file(folder, name, "first")
			import_file_by_path(path)
			frappe.db.delete("Migration Hash", {"file_path": get_relative_file_path(path)})

			write_note_file(folder, name, "second")
			self.assertTrue(import_file_by_path(path))
			self.assertEqual(frappe.db.get_value("Note", name, "content"), "second")
			self.assertEqual(get_migration_hash(path), calculate_hash(path))
			self.assertFalse(import_file_by_path(path))

	def test_site_edit_newer_than_file_is_kept(self):
		name = "_Test Migration Hash Site Edit"
		with tempfile.TemporaryDirectory() as folder:
			path = write_note_file(folder, name, "first")
			import_file_by_path(path)
			frappe.db.set_value("Note", name, "content", "site edit")

			write_note_file(folder, name, "second")
			self.assertFalse(import_file_by_path(path))
			self.assertEqual(frappe.db.get_value("Note", name, "content"), "site edit")

	def test_file_path_longer_than_an_indexed_column_is_stored(self):
		name = "_Test Migration Hash Long Path"
		with tempfile.TemporaryDirectory() as folder:
			long_folder = os.path.join(folder, "x" * 140, "x" * 140)
			os.makedirs(long_folder)
			path = write_note_file(long_folder, name, "first")
			self.assertGreater(len(get_relative_file_path(path)), 255)

			self.assertTrue(import_file_by_path(path))
			self.assertEqual(get_migration_hash(path), calculate_hash(path))

	def test_files_holding_the_same_record_keep_their_own_hash(self):
		name = "_Test Migration Hash Duplicate"
		with tempfile.TemporaryDirectory() as first_folder, tempfile.TemporaryDirectory() as second_folder:
			first_path = write_note_file(first_folder, name, "first")
			second_path = write_note_file(second_folder, name, "second")
			import_file_by_path(first_path)
			import_file_by_path(second_path)

			self.assertFalse(import_file_by_path(first_path))
			self.assertFalse(import_file_by_path(second_path))
			self.assertNotEqual(get_migration_hash(first_path), get_migration_hash(second_path))
