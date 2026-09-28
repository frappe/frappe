# /desk-architecture: only in developer mode, and only for a System Manager.

from unittest.mock import patch

import frappe
from frappe.tests import IntegrationTestCase
from frappe.utils import set_request
from frappe.website.page_renderers.desk_architecture_page import DeskArchitecturePage
from frappe.website.path_resolver import PathResolver
from frappe.website.serve import get_response


class TestDeskArchitecturePage(IntegrationTestCase):
	def setUp(self):
		self.addCleanup(frappe.set_user, "Administrator")
		self.enterContext(patch.dict(frappe.conf, {"developer_mode": 1}))

	def tearDown(self):
		if hasattr(frappe.local, "request"):
			delattr(frappe.local, "request")

	def open_page(self, user):
		frappe.set_user(user)
		set_request(method="GET", path="/desk-architecture")
		return get_response()

	def test_the_route_does_not_exist_outside_developer_mode(self):
		with patch.dict(frappe.conf, {"developer_mode": 0}):
			renderer = PathResolver("desk-architecture").resolve()[1]
		self.assertNotIsInstance(renderer, DeskArchitecturePage)

	def test_a_guest_is_sent_to_login(self):
		response = self.open_page("Guest")
		self.assertIn(response.status_code, (301, 302))
		self.assertIn("/login?redirect-to=/desk-architecture", response.headers["Location"])

	def test_a_user_without_system_manager_is_refused(self):
		response = self.open_page(make_user("desk-architecture-reader@example.com").name)
		self.assertEqual(response.status_code, 403)

	def test_a_system_manager_sees_the_diagram(self):
		user = make_user("desk-architecture-admin@example.com")
		user.add_roles("System Manager")
		response = self.open_page(user.name)
		self.assertEqual(response.status_code, 200)
		page = response.get_data(as_text=True)
		self.assertIn("<title>Desk v2 architecture</title>", page)
		self.assertIn('"id":"main"', page)


def make_user(email):
	return frappe.get_doc(
		doctype="User", email=email, first_name="Architecture", user_type="System User"
	).insert(ignore_if_duplicate=True)
