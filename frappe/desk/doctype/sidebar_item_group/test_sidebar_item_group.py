# Copyright (c) 2025, Frappe Technologies and Contributors
# See license.txt

from frappe.model.base_document import get_controller
from frappe.tests import IntegrationTestCase


class IntegrationTestSidebarItemGroup(IntegrationTestCase):
	def test_a_migrate_keeps_it(self):
		"""v16 sites hold these rows, and `remove_orphan_doctypes` deletes a doctype whose controller is gone."""
		for doctype in ("Sidebar Item Group", "Sidebar Item Group Link"):
			self.assertTrue(get_controller(doctype))
