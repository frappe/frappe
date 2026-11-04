# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

from unittest.mock import patch

from werkzeug.wrappers import Response

import frappe
from frappe.flow.launcher import add_to_page, get_app_roots
from frappe.flow.permissions import FLOW_USER_ROLE, ensure_flow_role
from frappe.flow.tests.test_permissions import _user
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.www.flow import index


class TestFlowPage(IntegrationTestCase):
	def setUp(self):
		# the page commits its CSRF token, which would keep the test's writes too
		self.enterContext(patch.object(frappe.db, "commit"))

	def tearDown(self):
		frappe.set_user("Administrator")
		frappe.db.rollback()

	def test_the_page_boots_a_user_and_sends_a_guest_to_login_and_back(self):
		boot = index.get_context(frappe._dict()).boot
		self.assertTrue(boot["csrf_token"])
		self.assertEqual(boot["site_name"], frappe.local.site)
		self.assertIn("socketio_port", boot)
		self.assertEqual(boot["flow_boot"]["user"]["name"], "Administrator")
		self.assertIn("agents", boot["flow_boot"])

		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		set_request(path="/flow/s/4uaiaqp7g3")
		frappe.set_user("Guest")
		with self.assertRaises(frappe.Redirect):
			index.get_context(frappe._dict())
		# back to the chat asked for, not just the page
		self.assertEqual(frappe.local.flags.redirect_location, "/login?redirect-to=%2Fflow%2Fs%2F4uaiaqp7g3")

	def test_the_launcher_joins_app_pages_of_flow_users(self):
		self.addCleanup(setattr, frappe.local, "request", getattr(frappe.local, "request", None))
		ensure_flow_role()
		member = _user("flow-launcher-member@example.com", FLOW_USER_ROLE)
		outsider = _user("flow-launcher-none@example.com")

		def page(path):
			set_request(path=path)
			response = Response("<html><body><p>page</p></body></html>", mimetype="text/html")
			add_to_page(response, frappe.local.request)
			return response.get_data(as_text=True)

		frappe.set_user(member)
		assets = {
			"frappe.flow.chat.island.js": "/assets/frappe/dist/flow/frappe.flow.chat.island.ABC.js",
			"frappe.flow.chat.island.css": "/assets/frappe/dist/flow/frappe.island.DEF.css",
		}
		with patch("frappe.flow.launcher.get_assets_json", return_value=assets):
			self.assertRegex(
				page("/desk/user"),
				r'<p>page</p><script src="[^"]+flow_launcher\.bundle[^"]*" defer'
				r' data-island="/assets/frappe/dist/flow/frappe\.flow\.chat\.island\.ABC\.js"'
				r' data-island-css="/assets/frappe/dist/flow/frappe\.island\.DEF\.css"></script></body>',
			)
		# not on the website, nor on /flow itself
		self.assertNotIn("flow_launcher", page("/about"))
		self.assertNotIn("flow_launcher", page("/flow"))
		# nor in Raven, which has an integration of its own
		with patch("frappe.get_hooks", return_value=[{"route": "/desk"}, {"route": "/raven"}]):
			self.assertEqual(get_app_roots(), {"desk", "studio"})
			self.assertNotIn("flow_launcher", page("/raven/channel/general"))
		# nor for anyone who may not use Flow
		for user in (outsider, "Guest"):
			frappe.set_user(user)
			self.assertNotIn("flow_launcher", page("/desk/user"))
