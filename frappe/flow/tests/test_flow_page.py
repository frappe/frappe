# Copyright (c) 2026, Frappe Technologies and contributors
# License: MIT. See LICENSE

import html
import json
import re
from unittest.mock import patch

from werkzeug.wrappers import Response

import frappe
from frappe.flow.api import boot
from frappe.flow.launcher import HIDDEN_KEY, add_to_page, set_hidden
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
		translation = {"doctype": "Translation", "language": "de", "source_text": "Hide Flow icon"}
		frappe.get_doc({**translation, "translated_text": "Flow-Symbol ausblenden"}).insert()
		self.addCleanup(frappe.translate.clear_cache)  # translations cached before the rollback

		def page(path):
			set_request(path=path)
			response = Response("<html><body><p>page</p></body></html>", mimetype="text/html")
			add_to_page(response, frappe.local.request)
			return response.get_data(as_text=True)

		frappe.set_user(member)
		self.assertRegex(
			page("/desk/user"),
			r'<p>page</p><script src="[^"]+flow_launcher\.bundle[^"]*" data-labels="[^"]+" defer></script></body>',
		)
		# its words in the user's language, which the apps' pages can't translate
		self.addCleanup(setattr, frappe.local, "lang", frappe.local.lang)
		frappe.local.lang = "de"
		labels = re.search(r'data-labels="([^"]+)"', page("/desk/user"))[1]
		self.assertEqual(json.loads(html.unescape(labels))["hide"], "Flow-Symbol ausblenden")
		# not on the website, nor on /flow itself
		self.assertNotIn("flow_launcher", page("/about"))
		self.assertNotIn("flow_launcher", page("/flow"))
		# nor for a user who hid it, until /flow's settings show it again
		self.addCleanup(frappe.defaults.clear_user_default, HIDDEN_KEY, member)  # the cached defaults
		set_hidden(True)
		self.assertNotIn("flow_launcher", page("/desk/user"))
		self.assertTrue(boot()["launcher_hidden"])
		set_hidden(False)
		self.assertIn("flow_launcher", page("/desk/user"))
		self.assertFalse(boot()["launcher_hidden"])
		# nor for anyone who may not use Flow
		for user in (outsider, "Guest"):
			frappe.set_user(user)
			self.assertNotIn("flow_launcher", page("/desk/user"))

	def test_the_dev_boot_needs_developer_mode(self):
		with patch.dict(frappe.local.conf, {"developer_mode": 0}):
			with self.assertRaises(frappe.PermissionError):
				index.get_context_for_dev()
		with patch.dict(frappe.local.conf, {"developer_mode": 1}):
			self.assertIn("flow_boot", index.get_context_for_dev())
