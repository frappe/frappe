# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.navigation_item.links import default_new_tab
from frappe.tests import UnitTestCase

SITE = "https://crm.example.com"


class TestDefaultNewTab(UnitTestCase):
	"""Whether a link leaves the app, without a site."""

	def test_another_origin_opens_in_a_new_tab(self):
		self.assertEqual(default_new_tab("https://frappe.io/docs", SITE), 1)

	def test_the_sites_own_absolute_url_stays_in_place(self):
		self.assertEqual(default_new_tab(f"{SITE}/crm/deals", SITE), 0)

	def test_another_scheme_on_the_same_host_is_another_origin(self):
		self.assertEqual(default_new_tab("http://crm.example.com/deals", SITE), 1)

	def test_a_path_stays_in_place(self):
		self.assertEqual(default_new_tab("/crm/deals", SITE), 0)

	def test_a_settings_hash_stays_in_place(self):
		self.assertEqual(default_new_tab("#settings/general", SITE), 0)

	def test_an_empty_url_stays_in_place(self):
		self.assertEqual(default_new_tab("", SITE), 0)

	def test_a_port_is_part_of_the_origin(self):
		"""The dev preview and the site it points at differ by port alone."""
		self.assertEqual(default_new_tab("https://crm.example.com:8080/x", SITE), 1)
