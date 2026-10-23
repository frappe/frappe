import tempfile
from pathlib import Path
from unittest.mock import patch

from babel.messages.catalog import Catalog
from babel.messages.pofile import read_po, write_po

import frappe
from frappe.gettext.translate import (
	generate_pot,
	get_is_gitignored_function_for_app,
	get_method_map,
	get_mo_path,
	get_po_path,
	get_pot_path,
	migrate,
	new_catalog,
	new_po,
	write_binary,
	write_catalog,
)
from frappe.tests import IntegrationTestCase

GITIGNORED_FILE = "frappe/public/dist/test_translate_test_gitignore.js"


class TestTranslate(IntegrationTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()

		gitignored_file = Path(frappe.get_app_source_path("frappe", GITIGNORED_FILE))
		gitignored_file.parent.mkdir(parents=True, exist_ok=True)
		gitignored_file.write_text('__("test_translate_test_gitignore")')

		get_pot_path("frappe").unlink(missing_ok=True)
		try:
			generate_pot("frappe")
		finally:
			gitignored_file.unlink()

	def test_generate_pot(self):
		pot_path = get_pot_path("frappe")

		self.assertTrue(pot_path.exists())
		self.assertIn("msgid", pot_path.read_text())

	def test_write_catalog(self):
		po_path = get_po_path("frappe", "test")
		po_path.unlink(missing_ok=True)

		catalog = new_catalog("frappe", "test")
		write_catalog("frappe", catalog, "test")

		self.assertTrue(po_path.exists())
		self.assertIn("msgid", po_path.read_text())

	def test_write_binary(self):
		mo_path = get_mo_path("frappe", "test")
		mo_path.unlink(missing_ok=True)

		catalog = new_catalog("frappe", "test")
		write_binary("frappe", catalog, "test")

		self.assertTrue(mo_path.exists())

	def test_get_method_map(self):
		method_map = get_method_map("frappe")
		self.assertTrue(len(method_map) > 0)
		self.assertTrue(len(method_map[0]) == 2)
		self.assertTrue(isinstance(method_map[0][0], str))
		self.assertTrue(isinstance(method_map[0][1], str))

	def test_new_po(self):
		po_path = get_po_path("frappe", "test")
		po_path.unlink(missing_ok=True)

		new_po("test", target_app="frappe")

		self.assertTrue(po_path.exists())
		self.assertIn("msgid", po_path.read_text())

	def test_migrate_csv_to_po(self):
		with tempfile.TemporaryDirectory() as app_path:
			app_path = Path(app_path)
			locale_dir = app_path / "locale"
			locale_dir.mkdir()
			catalog = Catalog()
			for message in ("% Billed", "From Dash", "From Underscore"):
				catalog.add(message)
			with (locale_dir / "main.pot").open("wb") as pot_file:
				write_po(pot_file, catalog)

			translations_dir = app_path / "translations"
			translations_dir.mkdir()
			(translations_dir / "zh-TW.csv").write_text(
				'"% Billed","% verrechnet"\n"From Dash","Mit Bindestrich"\n'
			)
			(translations_dir / "zh_tw.csv").write_text('"From Underscore","Mit Unterstrich"\n')

			with patch("frappe.gettext.translate.frappe.get_app_path", return_value=str(app_path)):
				migrate("frappe")

			with (locale_dir / "zh_TW.po").open("rb") as po_file:
				catalog = read_po(po_file)

			self.assertEqual(catalog.get("% Billed").string, "% verrechnet")
			self.assertEqual(catalog.get("From Dash").string, "Mit Bindestrich")
			self.assertEqual(catalog.get("From Underscore").string, "Mit Unterstrich")

	def test_migrate_csv_to_po_canonical_locale(self):
		with tempfile.TemporaryDirectory() as app_path:
			app_path = Path(app_path)
			locale_dir = app_path / "locale"
			locale_dir.mkdir()
			catalog = Catalog()
			catalog.add("Loan")
			with (locale_dir / "main.pot").open("wb") as pot_file:
				write_po(pot_file, catalog)

			translations_dir = app_path / "translations"
			translations_dir.mkdir()
			(translations_dir / "zh_tw.csv").write_text('"Loan","借款"\n')

			with patch("frappe.gettext.translate.frappe.get_app_path", return_value=str(app_path)):
				migrate("frappe")

			self.assertEqual([po.name for po in locale_dir.glob("*.po")], ["zh_TW.po"])

	def test_migrate_csv_to_po_keeps_existing_po(self):
		with tempfile.TemporaryDirectory() as app_path:
			app_path = Path(app_path)
			locale_dir = app_path / "locale"
			locale_dir.mkdir()
			catalog = Catalog()
			for message in ("Loan", "New Message"):
				catalog.add(message)
			with (locale_dir / "main.pot").open("wb") as pot_file:
				write_po(pot_file, catalog)

			catalog = Catalog(locale="de")
			catalog.add("Loan", "Darlehen")
			with (locale_dir / "de.po").open("wb") as po_file:
				write_po(po_file, catalog)

			translations_dir = app_path / "translations"
			translations_dir.mkdir()
			(translations_dir / "de.csv").write_text('"Loan","Kredit"\n"New Message","Neue Nachricht"\n')

			with patch("frappe.gettext.translate.frappe.get_app_path", return_value=str(app_path)):
				migrate("frappe")

			with (locale_dir / "de.po").open("rb") as po_file:
				catalog = read_po(po_file)

			self.assertEqual(catalog.get("Loan").string, "Darlehen")
			self.assertEqual(catalog.get("New Message").string, "Neue Nachricht")

	def test_migrate_csv_to_po_without_translations(self):
		with tempfile.TemporaryDirectory() as app_path:
			with patch("frappe.gettext.translate.frappe.get_app_path", return_value=app_path):
				migrate("frappe", "de")

			self.assertFalse((Path(app_path) / "locale").exists())

	def test_gitignore(self):
		is_gitignored = get_is_gitignored_function_for_app("frappe")

		file_name = GITIGNORED_FILE
		file_path = frappe.get_app_source_path("frappe", file_name)
		self.assertTrue(is_gitignored("frappe/public/node_modules"))
		self.assertTrue(is_gitignored("frappe/public/dist"))
		self.assertTrue(is_gitignored("frappe/public/dist/sub"))
		self.assertTrue(is_gitignored(file_name))
		self.assertTrue(is_gitignored(file_path))
		self.assertFalse(is_gitignored("frappe/public/dist2"))
		self.assertFalse(is_gitignored("frappe/public/dist2/sub"))

		self.assertNotIn("test_translate_test_gitignore", get_pot_path("frappe").read_text())

		self.assertTrue(get_is_gitignored_function_for_app(None)("frappe/public/dist"))
