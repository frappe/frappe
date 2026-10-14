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
		self.user = "mcp.transport@example.com"
		if not frappe.db.exists("User", self.user):
			frappe.get_doc(
				doctype="User", email=self.user, first_name="MCP Transport", send_welcome_email=0
			).insert()
		keys = generate_keys(self.user)
		self.authorization = f"token {keys['api_key']}:{keys['api_secret']}"
		self.site = frappe.local.site

	def request(self, payload=None, *, method="POST", headers=None, body=None, path="/api/v2/mcp", auth=True):
		request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
		if auth:
			request_headers["Authorization"] = self.authorization
		request_headers.update(headers or {})
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

	def ping(self, **kwargs):
		return self.request({"jsonrpc": "2.0", "id": 1, "method": "ping"}, **kwargs)
