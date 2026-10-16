# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and Contributors
# License: MIT. See LICENSE

import json

import frappe
from frappe.core.doctype.user.user import generate_keys
from frappe.tests import IntegrationTestCase
from frappe.tests.test_api import make_request
from frappe.utils import get_test_client


class McpTestCase(IntegrationTestCase):
	def setUp(self):
		super().setUp()
		frappe.set_user("Administrator")
		self.user, self.authorization = self.create_user("MCP Transport")
		self.site = frappe.local.site

	def create_user(self, first_name):
		if not frappe.db.exists("Role", "MCP Desk Tester"):
			frappe.get_doc(doctype="Role", role_name="MCP Desk Tester", desk_access=1).insert()
		user = f"mcp.{frappe.generate_hash(length=10)}@example.com"
		frappe.get_doc(
			doctype="User",
			email=user,
			first_name=first_name,
			send_welcome_email=0,
			roles=[{"role": "MCP Desk Tester"}],
		).insert()
		self.addCleanup(self.delete_user, user)
		keys = generate_keys(user)
		return user, f"token {keys['api_key']}:{keys['api_secret']}"

	def delete_user(self, user):
		frappe.set_user("Administrator")
		frappe.delete_doc_if_exists("User", user)
		frappe.db.commit()  # nosemgrep

	def request(self, payload=None, *, method="POST", headers=None, body=None, path="/api/v2/mcp", auth=True):
		request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
		if auth:
			request_headers["Authorization"] = self.authorization
		request_headers.update(headers or {})
		# The request uses another connection, which needs committed credentials and fixtures.
		frappe.db.commit()  # nosemgrep
		try:
			return make_request(
				get_test_client(use_cookies=False).open,
				args=(),
				kwargs={
					"path": path,
					"method": method,
					"headers": request_headers,
					"data": body if body is not None else json.dumps(payload),
				},
				site=self.site,
			)
		finally:
			# Discard the parent connection's snapshot before inspecting request writes.
			frappe.db.rollback()

	def ping(self, **kwargs):
		return self.request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, **kwargs)
