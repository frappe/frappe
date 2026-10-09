# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import frappe
from frappe.mcp.test_utils import McpTestCase


class TestApiV2UpdatePermissions(McpTestCase):
	def setUp(self):
		super().setUp()
		self.names = []
		for allocated_to in (self.user, None):
			doc = frappe.get_doc(
				doctype="ToDo", description="API v2 permission fixture", allocated_to=allocated_to
			).insert()
			self.names.append(doc.name)

	def tearDown(self):
		try:
			frappe.set_user("Administrator")
			for name in self.names:
				frappe.delete_doc_if_exists("ToDo", name)
			frappe.db.commit()  # nosemgrep
		finally:
			super().tearDown()

	def test_update_cannot_grant_access_using_payload(self):
		name = self.names[1]
		for field in ("allocated_to", "assigned_by", "owner"):
			with self.subTest(field=field):
				before = frappe.db.get_value("ToDo", name, field)
				response = self.request(
					{field: self.user}, method="PUT", path=f"/api/v2/document/ToDo/{name}"
				)
				self.assertEqual(response.status_code, 403)
				self.assertEqual(frappe.db.get_value("ToDo", name, field), before)

	def test_permitted_update_still_succeeds(self):
		name = self.names[0]
		response = self.request(
			{"description": "Permitted API update"}, method="PUT", path=f"/api/v2/document/ToDo/{name}"
		)
		self.assertEqual(response.status_code, 200)
		self.assertEqual(frappe.db.get_value("ToDo", name, "description"), "Permitted API update")
