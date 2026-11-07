from pathlib import Path
from tempfile import TemporaryDirectory

import frappe
from frappe.studio.utils import find_script_file, script_extension, validate_one_script_file
from frappe.tests import UnitTestCase


class TestUtils(UnitTestCase):
	def test_repository_scripts_default_to_typescript(self):
		with TemporaryDirectory() as folder:
			for stem in ("board", "router"):
				self.assertEqual(script_extension(folder, stem), "ts")
				self.assertEqual(find_script_file(folder, stem), str(Path(folder, f"{stem}.ts")))
				# A database app's script is JavaScript, so its export asks for `js`.
				self.assertEqual(script_extension(folder, stem, "js"), "js")

	def test_existing_scripts_keep_their_extension(self):
		for stem in ("board", "router"):
			for extension in ("js", "ts"):
				with self.subTest(stem=stem, extension=extension), TemporaryDirectory() as folder:
					path = Path(folder, f"{stem}.{extension}")
					path.write_text("export default {}")
					self.assertEqual(script_extension(folder, stem, "js"), extension)
					self.assertEqual(find_script_file(folder, stem), str(path))

	def test_a_companion_is_rejected_on_write_and_ignored_on_read(self):
		with TemporaryDirectory() as folder:
			for stem in ("board", "router"):
				Path(folder, f"{stem}.js").touch()
				with self.subTest(stem=stem):
					with self.assertRaisesRegex(frappe.ValidationError, "Keep only one"):
						validate_one_script_file(folder, f"{stem}.ts")

					# Reading prefers TypeScript, so a build never fails over a file it does not use.
					Path(folder, f"{stem}.ts").touch()
					self.assertEqual(find_script_file(folder, stem), str(Path(folder, f"{stem}.ts")))

			# A file in another language is not a companion.
			Path(folder, "theme.ts").touch()
			validate_one_script_file(folder, "theme.css")
