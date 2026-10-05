# Copyright (c) 2026, Frappe Technologies and Contributors
# See license.txt

import json

import frappe
from frappe.desk.doctype.desktop_layout.desktop_layout import save_layout
from frappe.desk.doctype.workspace.workspace import triage_module
from frappe.tests import IntegrationTestCase


class IntegrationTestDesktopLayout(IntegrationTestCase):
	def test_save_returns_the_module_a_new_workspace_landed_in(self):
		"""The grid's create dialog sends no module and the server picks one, so the client needs
		it back to route the new icon before a reload."""
		title = "Test Grid Created Workspace"
		self.addCleanup(frappe.delete_doc, "Workspace", title, force=True, ignore_missing=True)
		self.addCleanup(frappe.delete_doc, "Desktop Icon", title, force=True, ignore_missing=True)

		response = save_layout(
			user="Administrator",
			layout="[]",
			new_icons=json.dumps([{"workspace": {"label": title, "public": 1}}]),
		)

		self.assertEqual(response["workspace_modules"], {title: triage_module()})
		self.assertEqual(frappe.db.get_value("Workspace", title, "module"), triage_module())
