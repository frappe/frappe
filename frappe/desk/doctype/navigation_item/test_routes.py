# Copyright (c) 2026, Frappe Technologies and Contributors
# License: MIT. See LICENSE

from frappe.desk.doctype.navigation_item.routes import doctype_route
from frappe.tests import UnitTestCase


class TestDoctypeRoute(UnitTestCase):
	def test_a_doctype_opens_at_its_own_segment(self):
		self.assertEqual(doctype_route("Note"), "/Note")

	def test_a_name_with_a_space_is_encoded(self):
		"""The client reads the segment back with `decodeURIComponent`."""
		self.assertEqual(doctype_route("CRM Deal"), "/CRM%20Deal")

	def test_a_slash_in_a_name_stays_one_segment(self):
		self.assertEqual(doctype_route("A/B"), "/A%2FB")
