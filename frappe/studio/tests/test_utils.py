from pathlib import Path
from tempfile import TemporaryDirectory

import frappe
from frappe.studio.utils import find_script_file, script_extension, validate_one_script_file
from frappe.tests import UnitTestCase


class TestUtils(UnitTestCase):
	def test_repository_scripts_default_to_typescript(self):
		with TemporaryDirectory() as folder:
			self.assertEqual(script_extension(folder, "board"), "ts")
			self.assertEqual(find_script_file(folder, "board"), str(Path(folder, "board.ts")))
			self.assertEqual(script_extension(folder, "board", "js"), "js")

	def test_existing_scripts_keep_their_extension(self):
		for extension in ("js", "ts"):
			with self.subTest(extension=extension), TemporaryDirectory() as folder:
				path = Path(folder, f"board.{extension}")
				path.write_text("export default {}")
				self.assertEqual(script_extension(folder, "board", "js"), extension)
				self.assertEqual(find_script_file(folder, "board"), str(path))

	def test_a_companion_is_rejected_on_write_and_ignored_on_read(self):
		with TemporaryDirectory() as folder:
			Path(folder, "board.js").touch()
			with self.assertRaisesRegex(frappe.ValidationError, "Keep only one"):
				validate_one_script_file(folder, "board.ts")
			Path(folder, "board.ts").touch()
			self.assertEqual(find_script_file(folder, "board"), str(Path(folder, "board.ts")))
			Path(folder, "theme.ts").touch()
			validate_one_script_file(folder, "theme.css")
