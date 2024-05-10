from frappe.gettext.translate import (
	generate_pot,
	get_method_map,
	get_mo_path,
	get_po_path,
	get_pot_path,
	new_catalog,
	new_po,
	write_binary,
	write_catalog,
)
from frappe.tests.utils import FrappeTestCase


class TestTranslate(FrappeTestCase):
	def setUp(self):
		pass

	def tearDown(self):
		pass

	def test_generate_pot(self):
		pot_path = get_pot_path("frappe")
		pot_path.unlink(missing_ok=True)

		generate_pot("frappe")

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
